"""Testes para o modelo de fila/estado por guild do cog de musica."""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SPOTIPY_CLIENT_ID", "test-id")
os.environ.setdefault("SPOTIPY_CLIENT_SECRET", "test-secret")
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

import discord

from cogs import music


def _fake_resolved(track, **kwargs):
    """Simula uma resolucao yt-dlp: URL valida com 'expire' no futuro."""
    track.stream_url = (
        "https://cdn.example.com/video?expire=%d" % (int(time.time()) + 3600)
    )
    track.resolved_at = time.monotonic()
    track.title = track.query
    return track


async def _fake_resolve(track, **kwargs):
    return _fake_resolved(track, **kwargs)


class DummyPostgres:
    def query(self, *args, **kwargs):
        return []

    def update(self, *args, **kwargs):
        return 1

    async def aquery(self, *args, **kwargs):
        return []

    async def aupdate(self, *args, **kwargs):
        return 1


class FakeSource:
    def __init__(self):
        self.volume = 0.5


class FakeVoice:
    def __init__(self):
        self.source = None
        self.played = None
        self.after = None
        self._playing = False
        self._paused = False
        self.disconnected = False
        self.stopped = False
        self.channel = None

    def play(self, source, after=None):
        self.source = source
        self.played = source
        self.after = after
        self._playing = True

    def is_connected(self):
        return not self.disconnected

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def pause(self):
        self._playing = False
        self._paused = True

    def resume(self):
        self._paused = False
        self._playing = True

    def stop(self):
        self.stopped = True
        self._playing = False

    async def disconnect(self):
        self.disconnected = True
        self._playing = False


def make_cog(monkeypatch):
    monkeypatch.setattr(music, "Postgres", lambda: DummyPostgres())
    return music.Music(bot=None)


def test_state_is_isolated_per_guild(monkeypatch):
    cog = make_cog(monkeypatch)
    g1 = cog._state(1)
    g2 = cog._state(2)
    assert g1 is not g2
    assert cog._state(1) is g1
    assert g1.queue == [] and g2.queue == []


def test_enqueue_front_and_back(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)

    asyncio.run(cog._enqueue(state, [music.Track("a"), music.Track("b")], front=False))
    asyncio.run(cog._enqueue(state, [music.Track("c")], front=True))

    assert [t.query for t in state.queue] == ["c", "a", "b"]


def test_enqueue_respects_max_queue(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.queue = [music.Track(str(i)) for i in range(music.MAX_QUEUE)]

    added = asyncio.run(cog._enqueue(state, [music.Track("overflow")], front=False))

    assert added == 0
    assert len(state.queue) == music.MAX_QUEUE


def test_is_url():
    assert music._is_url("https://www.youtube.com/watch?v=abc")
    assert not music._is_url("just a search term")
    assert not music._is_url("")


def test_parse_timestamp():
    assert music._parse_timestamp("90") == 90
    assert music._parse_timestamp("1:30") == 90
    assert music._parse_timestamp("0:01:30") == 90
    assert music._parse_timestamp("1:02:03") == 3723
    assert music._parse_timestamp(" 2:00 ") == 120
    assert music._parse_timestamp("0") == 0


def test_parse_timestamp_invalid():
    assert music._parse_timestamp("") is None
    assert music._parse_timestamp("abc") is None
    assert music._parse_timestamp("1:") is None
    assert music._parse_timestamp(":30") is None
    assert music._parse_timestamp("1:2:3:4") is None
    assert music._parse_timestamp("1:a") is None
    assert music._parse_timestamp("-30") is None


def test_build_source_wraps_in_volume_transformer(monkeypatch):
    """source precisa ser um PCMVolumeTransformer, senao _apply_volume nao faz nada."""
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.volume = 0.25
    track = music.Track("x")
    track.stream_url = "https://cdn.example.com/x"

    class FakeFFmpeg(discord.AudioSource):
        def read(self):
            return b""

    created = {}

    def fake_ffmpeg(url, **options):
        created["url"] = url
        return FakeFFmpeg()

    monkeypatch.setattr(music.discord, "FFmpegPCMAudio", fake_ffmpeg)

    source = cog._build_source(track, state)

    assert isinstance(source, discord.PCMVolumeTransformer)
    assert isinstance(source.original, FakeFFmpeg)
    assert source.volume == 0.25
    assert created["url"] == "https://cdn.example.com/x"


def test_advance_plays_next_and_keeps_queue(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("first"), music.Track("second")]

    cog._resolve_track = _fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._advance_locked(1, state))

    assert state.current is not None
    assert state.current.query == "first"
    assert [t.query for t in state.queue] == ["second"]
    assert state.voice.played is not None


def test_resolve_failure_skips_to_next(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("bad"), music.Track("good")]

    async def fake_resolve(track, **kwargs):
        if track.query == "bad":
            return None
        return _fake_resolved(track, **kwargs)

    cog._resolve_track = fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._advance_locked(1, state))

    assert state.current.query == "good"
    assert state.queue == []


def test_on_track_end_advances_queue(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.current = music.Track("current")
    state.queue = [music.Track("next")]

    cog._resolve_track = _fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._on_track_end(1))

    assert state.current.query == "next"
    assert state.queue == []


def test_on_track_end_disconnects_when_empty(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.current = music.Track("current")

    asyncio.run(cog._on_track_end(1))

    assert state.current is None
    assert state.voice is None


def test_stop_clears_state(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    fake_voice = FakeVoice()
    state.voice = fake_voice
    state.current = music.Track("current")
    state.queue = [music.Track("a"), music.Track("b")]

    asyncio.run(cog._disconnect_nolock(1, state))

    assert state.current is None
    assert state.queue == []
    assert state.voice is None
    assert fake_voice.disconnected


def test_abort_resolution_sets_event_and_reports(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)

    state.resolving = True
    assert cog._abort_resolution(state) is True
    assert state.abort_event.is_set()

    state.resolving = False
    assert cog._abort_resolution(state) is False
    assert state.abort_event.is_set()


def test_advance_locked_stops_on_resolution_aborted(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("loading"), music.Track("next")]

    async def fake_resolve(track, **kwargs):
        event = kwargs.get("abort_event")
        if event is not None:
            event.set()
        raise music.ResolutionAborted(track.query)

    cog._resolve_track = fake_resolve

    asyncio.run(cog._advance_locked(1, state))

    assert state.voice.played is None
    assert state.current is None
    assert [t.query for t in state.queue] == ["next"]
    assert state.resolving is False


def test_on_track_end_ignores_stale_generation(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.current = music.Track("current")
    state.queue = [music.Track("next")]
    state.play_generation = 5

    asyncio.run(cog._on_track_end(1, generation=4))

    assert state.current.query == "current"
    assert [t.query for t in state.queue] == ["next"]


def test_sync_voice_discards_ghost(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    ghost = FakeVoice()
    ghost.disconnected = True
    state.voice = ghost

    class FakeGuild:
        id = 1
        voice_client = None

    assert cog._sync_voice(state, FakeGuild()) is False
    assert state.voice is None


def test_sync_voice_adopts_real_client(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    real = FakeVoice()
    real.channel = "canal"

    class FakeGuild:
        id = 1
        voice_client = real

    assert cog._sync_voice(state, FakeGuild()) is True
    assert state.voice is real
    assert state.voice_channel == "canal"


def test_url_expires_at_parses_expire(monkeypatch):
    assert music._url_expires_at("https://cdn.example.com/v?expire=4102444800") == 4102444800.0
    assert music._url_expires_at("https://cdn.example.com/v?expire=4102444800000") == 4102444800.0
    assert music._url_expires_at("https://cdn.example.com/v?expire=abc") is None
    assert music._url_expires_at("https://cdn.example.com/v") is None


def test_is_track_fresh_uses_expire_or_age(monkeypatch):
    future = "https://cdx.example.com/v?expire=%d" % (int(time.time()) + 3600)
    past = "https://cdx.example.com/v?expire=%d" % (int(time.time()) - 60)

    assert music._is_track_fresh(music.Track("a", stream_url=future)) is True
    assert music._is_track_fresh(music.Track("a", stream_url=past)) is False
    assert music._is_track_fresh(music.Track("a")) is False

    # Sem "expire", usa a idade maxima como fallback.
    fresh = music.Track("a", stream_url="https://c/v")
    fresh.resolved_at = time.monotonic()
    stale = music.Track("a", stream_url="https://c/v")
    stale.resolved_at = time.monotonic() - music.YTDLP_URL_MAX_AGE_SECONDS - 1
    assert music._is_track_fresh(fresh) is True
    assert music._is_track_fresh(stale) is False


def test_resolve_track_reuses_fresh_url(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    track.stream_url = (
        "https://c.example.com/v?expire=%d" % (int(time.time()) + 3600)
    )
    track.resolved_at = time.monotonic()

    calls = []

    async def boom(*args, **kwargs):
        calls.append(1)
        raise AssertionError("nao deveria re-resolver")

    monkeypatch.setattr(music, "_extract_info_isolated", boom)

    asyncio.run(cog._resolve_track(track))

    assert calls == []
    assert track.stream_url is not None


def test_resolve_track_refreshes_stale_url(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    track.stream_url = "https://c.example.com/v?expire=%d" % (int(time.time()) - 60)
    track.resolved_at = time.monotonic()

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        return {"url": "https://campo.example.com/v?expire=%d" % (int(time.time()) + 3600), "title": "nova"}

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    asyncio.run(cog._resolve_track(track))

    assert "campo.example.com" in track.stream_url
    assert track.title == "nova"
    assert track.resolved_at is not None


def test_on_track_end_retries_once_on_early_error(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.current = music.Track("fail")
    state.current.stream_url = "https://c.example.com/v?expire=%d" % (int(time.time()) + 3600)
    state.current.resolved_at = time.monotonic()
    state.queue = [music.Track("next")]

    cog._resolve_track = _fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._on_track_end(1, error=Exception("boom")))

    assert state.current.query == "fail"  # re-resolvida e tocada de novo
    assert state.current.retries == 1
    assert [t.query for t in state.queue] == ["next"]

    # Segunda falha no comeco: retries esgotado, avanca para a proxima.
    asyncio.run(cog._on_track_end(1, error=Exception("boom")))
    assert state.current.query == "next"
    assert state.queue == []


def test_on_track_end_no_retry_when_played_long(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.current = music.Track("long")
    state.started_at = time.monotonic() - music.PLAYBACK_START_THRESHOLD_SECONDS - 1
    state.queue = [music.Track("next")]

    cog._resolve_track = _fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._on_track_end(1, error=Exception("boom")))

    assert state.current.query == "next"
    assert state.queue == []


def test_is_bot_check():
    assert music._is_bot_check("ERROR: Sign in to confirm you're not a bot")
    assert music._is_bot_check("LOGIN_REQUIRED")
    assert not music._is_bot_check("Video unavailable")
    assert not music._is_bot_check("")


def _fake_extract_data():
    return {
        "url": "https://c.example.com/v?expire=%d" % (int(time.time()) + 3600),
        "title": "ok",
    }


def test_resolve_track_uses_cookies_when_available(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    monkeypatch.setattr(music, "_has_login_cookies", lambda: True)
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: False)

    calls = []

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        calls.append(use_cookies)
        return _fake_extract_data()

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    asyncio.run(cog._resolve_track(track))

    assert calls == [True]


def test_resolve_track_skips_cookies_when_rejected(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    monkeypatch.setattr(music, "_has_login_cookies", lambda: True)
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: True)

    calls = []

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        calls.append(use_cookies)
        return _fake_extract_data()

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    asyncio.run(cog._resolve_track(track))

    assert calls == [False]


def test_resolve_track_falls_back_without_cookies(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    monkeypatch.setattr(music, "_has_login_cookies", lambda: True)
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: False)
    monkeypatch.setattr(music, "_mark_cookies_rejected", lambda: True)

    calls = []

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        calls.append(use_cookies)
        if use_cookies:
            raise music.BotCheckError("sign in to confirm")
        return _fake_extract_data()

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    asyncio.run(cog._resolve_track(track))

    assert calls == [True, False]
    assert track.title == "ok"


def test_resolve_track_reraises_bot_check_without_cookies(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    monkeypatch.setattr(music, "_has_login_cookies", lambda: False)

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        raise music.BotCheckError("sign in to confirm")

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    raised = False
    try:
        asyncio.run(cog._resolve_track(track))
    except music.BotCheckError:
        raised = True
    assert raised


def test_has_login_cookies_false_without_file(monkeypatch, tmp_path):
    monkeypatch.setattr(music, "COOKIES_FILE", str(tmp_path / "missing.txt"))
    assert music._has_login_cookies() is False


def test_advance_locked_skips_track_on_bot_check(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("blocked"), music.Track("ok")]

    async def fake_resolve(track, **kwargs):
        if track.query == "blocked":
            raise music.BotCheckError("sign in to confirm")
        return _fake_resolved(track, **kwargs)

    cog._resolve_track = fake_resolve
    cog._build_source = lambda track, state, extra_before="": FakeSource()

    asyncio.run(cog._advance_locked(1, state))

    assert state.current.query == "ok"
    assert state.queue == []


def test_announce_shows_cookies_hint_when_rejected(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    track = music.Track("song")
    track.title = "song"
    track.webpage_url = "https://youtu.be/x"
    track.duration = 10

    sent = []

    class FakeChannel:
        async def send(self, embed=None, **kwargs):
            sent.append(embed)
            return "msg"

    state.channel = FakeChannel()
    monkeypatch.setattr(music, "guild_macro", lambda gid: "Fake")
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: True)

    asyncio.run(cog._announce_locked(1, state, track))

    assert sent and "mgy cookies" in sent[0].description


def test_announce_hides_cookies_hint_when_ok(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    track = music.Track("song")
    track.title = "song"
    track.webpage_url = "https://youtu.be/x"
    track.duration = 10

    sent = []

    class FakeChannel:
        async def send(self, embed=None, **kwargs):
            sent.append(embed)
            return "msg"

    state.channel = FakeChannel()
    monkeypatch.setattr(music, "guild_macro", lambda gid: "Fake")
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: False)

    asyncio.run(cog._announce_locked(1, state, track))

    assert sent and "mgy cookies" not in sent[0].description


class FakeEmbed:
    def __init__(self, description=""):
        self.description = description


class FakeMessage:
    def __init__(self, embed):
        self.embeds = [embed]
        self.edits = []

    async def edit(self, embed=None, **kwargs):
        self.edits.append(embed)
        self.embeds = [embed]


class FakeTypingChannel:
    def __init__(self):
        self.entered = 0
        self.exited = 0

    def typing(self):
        outer = self

        class _CM:
            async def __aenter__(self):
                outer.entered += 1

            async def __aexit__(self, *args):
                outer.exited += 1

        return _CM()


def test_resolve_track_marks_rejected_when_fallback_fails(monkeypatch):
    cog = make_cog(monkeypatch)
    track = music.Track("song")
    monkeypatch.setattr(music, "_has_login_cookies", lambda: True)
    monkeypatch.setattr(music, "_cookies_rejected_for_current_file", lambda: False)

    marked = []
    monkeypatch.setattr(music, "_mark_cookies_rejected", lambda: marked.append(1) or True)

    async def fake_extract(query, idle_timeout, max_timeout, abort_event, use_cookies=True):
        raise music.BotCheckError("sign in to confirm")

    monkeypatch.setattr(music, "_extract_info_isolated", fake_extract)

    raised = False
    try:
        asyncio.run(cog._resolve_track(track))
    except music.BotCheckError:
        raised = True

    assert raised
    assert marked == [1]  # marcou os cookies mesmo com o fallback falhando


def test_edit_now_playing_cookies_warning(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    msg = FakeMessage(FakeEmbed("tocando agora"))
    state.now_playing = msg

    asyncio.run(cog._edit_now_playing_cookies_warning(state))
    assert len(msg.edits) == 1
    assert "mgy cookies" in msg.edits[0].description

    # Nao duplica o aviso se chamado de novo.
    asyncio.run(cog._edit_now_playing_cookies_warning(state))
    assert len(msg.edits) == 1


def test_edit_now_playing_cookies_warning_without_message(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.now_playing = None
    asyncio.run(cog._edit_now_playing_cookies_warning(state))  # nao deve explodir


def test_resolve_for_playback_shows_typing(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    channel = FakeTypingChannel()
    state.channel = channel

    calls = []

    async def fake_resolve(track, **kwargs):
        calls.append(track.query)
        return _fake_resolved(track, **kwargs)

    cog._resolve_track = fake_resolve

    asyncio.run(cog._resolve_for_playback(state, music.Track("x")))

    assert channel.entered == 1
    assert channel.exited == 1
    assert calls == ["x"]


def test_advance_locked_edits_embed_on_bot_check(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("blocked")]
    msg = FakeMessage(FakeEmbed("tocando agora"))
    state.now_playing = msg

    async def fake_resolve(track, **kwargs):
        raise music.BotCheckError("sign in to confirm")

    cog._resolve_track = fake_resolve

    asyncio.run(cog._advance_locked(1, state))

    assert msg.edits
    assert "mgy cookies" in msg.edits[0].description
