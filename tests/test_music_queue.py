"""Testes para o modelo de fila/estado por guild do cog de musica."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SPOTIPY_CLIENT_ID", "test-id")
os.environ.setdefault("SPOTIPY_CLIENT_SECRET", "test-secret")
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

from cogs import music


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


def test_advance_plays_next_and_keeps_queue(monkeypatch):
    cog = make_cog(monkeypatch)
    state = cog._state(1)
    state.voice = FakeVoice()
    state.queue = [music.Track("first"), music.Track("second")]

    async def fake_resolve(track, **kwargs):
        track.stream_url = "stream"
        track.title = track.query
        return track

    cog._resolve_track = fake_resolve
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
        track.stream_url = "stream"
        track.title = track.query
        return track

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

    async def fake_resolve(track, **kwargs):
        track.stream_url = "stream"
        track.title = track.query
        return track

    cog._resolve_track = fake_resolve
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
