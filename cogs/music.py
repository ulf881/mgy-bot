"""
Modulo para comandos de musica.

O estado de cada guild vive em um unico objeto :class:`GuildPlayer` (fila,
musica atual, voice client, volume, etc). A fila so e alterada pelos caminhos
de cleanup: o avanco automatico ao terminar uma musica, os comandos ``skip`` e
``stop`` e, adicionalmente, ``limpar`` e a verificacao de inatividade.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import discord
import googleapiclient.discovery
import spotipy
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from spotipy.oauth2 import SpotifyClientCredentials

from utils.config import (
    AVATAR_URL,
    BONUS_ROOM_TITLE,
    BONUS_ROOM_URL,
    GARAGEM_TRACK_URL,
    MAX_QUEUE,
    guild_macro,
)
from utils.pgdatabase import Postgres

YTDLP_SLOW_STARTUP_SECONDS = 10
FFMPEG_SLOW_STARTUP_SECONDS = 5
YTDLP_EXTRACT_TIMEOUT_SECONDS = 45
MASHUP_SCAN_LIMIT = 100

COOKIES_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
)
DROPBOX_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Dropbox.html")
)

log = logging.getLogger("music")


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Dest": "audio",
    "Referer": "https://www.youtube.com/",
    "Origin": "https://www.youtube.com",
}

YOUTUBE_PLAYER_CLIENTS = ["web_embedded", "web", "tv", "mweb"]

ytdl_format_options = {
    "format": "bestaudio[ext=webm]/bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    # bind to ipv4 since ipv6 addresses cause issues sometimes
    "source_address": "0.0.0.0",
    "verbose": False,
    "socket_timeout": 15,
    "cookiefile": COOKIES_FILE,
    "http_headers": BROWSER_HEADERS,
    "extractor_args": {"youtube": {"player_client": YOUTUBE_PLAYER_CLIENTS}},
    "concurrent_fragment_downloads": 1,
}

ffmpeg_options = {
    "before_options": "-nostdin -re -probesize 32k -analyzeduration 0 -rw_timeout 15000000 -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_max_retries 3",
    "options": "-vn -sn -dn -threads 1 -filter_threads 1 -filter_complex_threads 1 -loglevel error -nostats",
}

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=os.environ["SPOTIPY_CLIENT_ID"],
        client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    )
)
youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    developerKey=os.environ["YOUTUBE_API_KEY"],
    cache_discovery=False,
)


@dataclass
class Track:
    """Uma musica na fila (ainda nao necessariamente resolvida)."""

    query: str
    is_search: bool = False
    title: str | None = None
    stream_url: str | None = None
    webpage_url: str | None = None
    duration: float | None = None
    data: dict | None = None

    def display_name(self) -> str:
        """Nome para exibir em listas, sem resolver novamente."""
        return self.title or self.query


@dataclass
class GuildPlayer:
    """Estado de reproducao independente de cada guild."""

    queue: list[Track] = field(default_factory=list)
    current: Track | None = None
    voice: discord.VoiceClient | None = None
    channel: discord.abc.Messageable | None = None
    now_playing: discord.Message | None = None
    volume: float = 0.5
    equalizer: str | None = None
    started_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_cookie_cache = {"mtime": None, "value": ""}
_mashups_cache: list[str] = []


def _extract_cookie_header(path: str) -> str:
    """Le o arquivo Netscape cookies e retorna o header Cookie (cacheado)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ""

    if _cookie_cache["mtime"] == mtime:
        return _cookie_cache["value"]

    cookie_pairs = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                fields = re.split(r"\s+", line)
                if len(fields) < 7:
                    continue

                domain, _, _, _, _, name, *rest = fields
                value = " ".join(rest) if rest else ""
                if not name or not value:
                    continue

                domain = domain.removeprefix(".")

                if domain in {
                    "youtube.com",
                    "google.com",
                    "googlevideo.com",
                } or domain.endswith(
                    (
                        ".youtube.com",
                        ".google.com",
                        ".googlevideo.com",
                        ".youtube-nocookie.com",
                    )
                ):
                    cookie_pairs.append(f"{name}={value}")
    except OSError:
        return ""

    seen = set()
    ordered = []
    for cookie in cookie_pairs:
        if cookie not in seen:
            seen.add(cookie)
            ordered.append(cookie)

    value = "; ".join(ordered)
    _cookie_cache["mtime"] = mtime
    _cookie_cache["value"] = value
    return value


def _build_ffmpeg_headers(data: dict) -> dict:
    """Constroi headers similares a um navegador para URLs do GoogleVideo."""
    headers = dict(BROWSER_HEADERS)
    yt_headers = data.get("http_headers") or {}
    headers.update({k: v for k, v in yt_headers.items() if v})

    if not headers.get("Referer") and data.get("webpage_url"):
        headers["Referer"] = data["webpage_url"]

    cookie_value = _extract_cookie_header(COOKIES_FILE)
    if cookie_value:
        headers["Cookie"] = cookie_value
    return headers


async def _extract_info_isolated(url: str) -> dict:
    """Extrai metadados em um subprocesso que pode ser morto sem travar o bot."""
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--no-check-certificates",
        "--default-search",
        "auto",
        "--socket-timeout",
        "15",
        "--format",
        ytdl_format_options["format"],
        "--source-address",
        ytdl_format_options["source_address"],
        "--extractor-args",
        "youtube:player_client=" + ",".join(YOUTUBE_PLAYER_CLIENTS),
    ]
    if os.path.exists(COOKIES_FILE):
        command.extend(["--cookies", COOKIES_FILE])
    command.append(url)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=YTDLP_EXTRACT_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise TimeoutError(
            f"yt-dlp extraction timed out after {YTDLP_EXTRACT_TIMEOUT_SECONDS}s"
        ) from exc

    if process.returncode != 0:
        error = stderr.decode(errors="replace").strip()
        raise RuntimeError(error or f"yt-dlp exited with {process.returncode}")

    try:
        return json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid JSON") from exc


def _is_url(value: str) -> bool:
    """Verifica se uma string e uma url."""
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def _load_mashups() -> list[str]:
    """Le os links de mashup do Dropbox.html uma unica vez."""
    global _mashups_cache
    if _mashups_cache:
        return _mashups_cache

    with open(DROPBOX_FILE, encoding="utf-8") as handle:
        soup = BeautifulSoup(handle, features="lxml")

    links = [link.get("href") for link in soup.find_all("a")]
    # retira os links que nao sao musica (cabecalho da pagina)
    links = [link for link in links if link][3:]
    _mashups_cache = links
    return _mashups_cache


class Music(commands.Cog):
    """Classe para comandos de musica."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pg = Postgres()
        self.players: dict[int, GuildPlayer] = {}

    # ------------------------------------------------------------------
    # Estado / utilitarios internos
    # ------------------------------------------------------------------
    def _state(self, guild_id: int) -> GuildPlayer:
        """Retorna (criando se necessario) o estado da guild."""
        state = self.players.get(guild_id)
        if state is None:
            state = GuildPlayer()
            self.players[guild_id] = state
        return state

    def _apply_volume(self, state: GuildPlayer):
        if state.voice is not None and state.voice.source is not None:
            state.voice.source.volume = state.volume

    async def _resolve_track(self, track: Track) -> Track | None:
        """Resolve uma Track via yt-dlp. Retorna None em caso de falha."""
        if track.stream_url:
            return track

        started_at = time.monotonic()
        try:
            data = await _extract_info_isolated(track.query)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error("Erro ao adquirir video da URL '%s': %s", track.query, e)
            return None

        if data and "entries" in data:
            entries = data.get("entries") or []
            data = entries[0] if entries else None
        if not data or not data.get("url"):
            log.warning("Nenhuma midia encontrada para '%s'", track.query)
            return None

        track.data = data
        track.title = data.get("title") or track.query
        track.duration = data.get("duration")
        track.stream_url = data.get("url")
        track.webpage_url = data.get("original_url") or track.webpage_url

        elapsed = time.monotonic() - started_at
        if elapsed >= YTDLP_SLOW_STARTUP_SECONDS:
            log.warning("yt-dlp startup levou %.1fs para %s", elapsed, track.query)
        return track

    def _build_source(self, track: Track, state: GuildPlayer, extra_before: str = ""):
        """Cria o FFmpegPCMAudio para uma Track ja resolvida."""
        options = ffmpeg_options.copy()
        before = options.get("before_options", "")

        if extra_before:
            before = f"{before} {extra_before}".strip()

        headers = _build_ffmpeg_headers(track.data or {})
        header_strings = [f"{key}: {value}" for key, value in headers.items() if value]
        if header_strings:
            combined_headers = "\r\n".join(header_strings) + "\r\n"
            before = f'{before} -headers "{combined_headers}"'.strip()

        options["before_options"] = before

        if state.equalizer:
            options["options"] = f"{options.get('options', '')} {state.equalizer}"

        return discord.FFmpegPCMAudio(track.stream_url, **options)

    async def _announce_locked(self, guild_id: int, state: GuildPlayer, track: Track):
        """Envia/edita a mensagem de 'tocando agora'."""
        if state.channel is None:
            return

        duration = int(track.duration or 0)
        minutes, seconds = divmod(duration, 60)
        description = f"[{track.title}]({track.webpage_url})"
        if track.is_search:
            description += f"\n Pesquisado: {track.query}"
        description += f"\n Duração: {minutes:02d}:{seconds:02d}"
        if state.queue:
            description += f"\nAinda na lista: {len(state.queue)}"

        embed = discord.Embed(description=description, colour=0xFA00D4)
        embed.set_footer(text=guild_macro(guild_id), icon_url=AVATAR_URL)

        if state.now_playing is not None:
            try:
                await state.now_playing.edit(embed=embed)
                return
            except discord.HTTPException:
                state.now_playing = None

        try:
            state.now_playing = await state.channel.send(embed=embed)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning("Erro ao enviar mensagem de reproducao: %s", e)

    async def _disconnect_nolock(self, guild_id: int, state: GuildPlayer):
        """Desconecta e limpa o estado. Deve ser chamado com o lock adquirido."""
        state.current = None
        state.queue.clear()
        state.now_playing = None
        state.started_at = 0.0
        voice = state.voice
        state.voice = None
        if voice is not None:
            try:
                await voice.disconnect()
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.warning("Erro ao desconectar (%s): %s", guild_id, e)

    async def _advance_locked(self, guild_id: int, state: GuildPlayer):
        """Toca a proxima faixa valida. Deve ser chamado com o lock adquirido."""
        if state.current is not None or state.voice is None:
            return

        while state.queue:
            track = state.queue.pop(0)
            resolved = await self._resolve_track(track)
            if resolved is None:
                continue

            try:
                source = self._build_source(resolved, state)
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error("Erro ao criar FFmpeg Audio para %s: %s", track.query, e)
                await asyncio.sleep(0.5)
                continue

            state.current = resolved
            state.started_at = time.monotonic()
            try:
                state.voice.play(source, after=self._make_after(guild_id))
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error("Erro ao tocar %s: %s", track.query, e)
                state.current = None
                await asyncio.sleep(1)
                continue

            self._apply_volume(state)
            log.info("Tocando %s", resolved.title)
            if resolved.title == BONUS_ROOM_TITLE:
                asyncio.create_task(self._enable_double_xp())
            await self._announce_locked(guild_id, state, resolved)
            return

        await self._disconnect_nolock(guild_id, state)

    def _make_after(self, guild_id: int):
        def after(error):
            if error:
                log.error("Player da guild %s terminou com erro: %s", guild_id, error)
            asyncio.run_coroutine_threadsafe(
                self._on_track_end(guild_id), self.bot.loop
            )

        return after

    async def _on_track_end(self, guild_id: int):
        """Avanca a fila quando uma musica termina (unico cleanup automatico)."""
        state = self._state(guild_id)
        async with state.lock:
            state.current = None
            await self._advance_locked(guild_id, state)

    async def _enable_double_xp(self):
        """Habilita por 29 segundos XP em dobro (Bonus Room)."""
        self.bot.bonusXP = True
        await asyncio.sleep(29)
        self.bot.bonusXP = False

    async def _change_volume(self, ctx: commands.Context, args, global_scope: bool):
        """Implementacao compartilhada de volume/globalvolume."""
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        scope = "global " if global_scope else ""

        if state.voice is None:
            return await ctx.send("O bot não está conectado em um canal de voz.")

        current_url = state.current.query if state.current else None
        if current_url == GARAGEM_TRACK_URL:
            state.volume = sys.float_info.max
            self._apply_volume(state)
            return await ctx.send("Lmao")

        volume = 50
        if args and args[0].isdigit() and int(args[0]) > 0:
            volume = int(args[0])

        invoked = ctx.invoked_with.lower()
        if ("-m" in args or "max" in args or "-max" in args) or invoked in {
            "volmax",
            "maxvol",
            "gvolmax",
            "gmaxvol",
            "alwaysvolmax",
        }:
            state.volume = sys.float_info.max
            self._apply_volume(state)
            await ctx.send("Dale Dale Dale" if global_scope else "Dale")
        elif "-r" in args or "reset" in args or "-reset" in args:
            state.volume = 50 / 100
            self._apply_volume(state)
            await ctx.send(f"Volume {scope}resetado")
        elif invoked in {"volmilas", "gvolmilas"}:
            amount = int(args[0]) if args and args[0].isdigit() else 1
            state.volume += (4.20 * amount) / 100
            self._apply_volume(state)
            await ctx.send(
                f"Volmilas subiu volume em 4.20% (x{amount}). "
                f"Atual {state.volume * 100:.1f}%"
            )
        else:
            state.volume = volume / 100
            self._apply_volume(state)
            await ctx.send(f"Volume {scope}trocado para {volume}%")

    async def _enqueue(self, state: GuildPlayer, tracks: list[Track], front: bool):
        """Adiciona tracks respeitando o limite maximo da fila."""
        available = MAX_QUEUE - len(state.queue)
        if available <= 0:
            log.warning("Fila cheia, ignorando novas musicas")
            return 0
        accepted = tracks[:available]
        if front:
            state.queue[0:0] = list(reversed(accepted))
        else:
            state.queue.extend(accepted)
        return len(accepted)

    # ------------------------------------------------------------------
    # Coleta de playlists
    # ------------------------------------------------------------------
    async def _spotify_tracks(self, url: str) -> list[Track]:
        """Separa musicas da playlist usando a api do spotify."""
        log.info("Buscando playlist do spotify: %s", url)

        response = await asyncio.to_thread(
            sp.playlist_tracks,
            url,
            limit=50,
            offset=0,
            fields="items.track.name,items.track.artists.name",
        )
        tracks = response["items"]
        offset = 0
        while len(response["items"]) >= 50:
            offset += 50
            response = await asyncio.to_thread(
                sp.playlist_tracks,
                url,
                offset=offset,
                limit=50,
                fields="items.track.name,items.track.artists.name",
            )
            tracks.extend(response["items"])

        result = []
        for item in tracks:
            artist = item["track"]["artists"][0]["name"]
            name = item["track"]["name"]
            result.append(Track(f"{artist} {name}", is_search=True))
        return result

    async def _youtube_playlist(self, url: str) -> list[Track]:
        """Separa musicas da playlist usando a api do youtube v3."""
        log.info("Buscando playlist do youtube: %s", url)
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        playlist_id = query["list"][0]

        request = youtube.playlistItems().list(
            part="snippet", playlistId=playlist_id, maxResults=50
        )
        response = await asyncio.to_thread(request.execute)

        playlist_items = []
        while request is not None:
            playlist_items += response["items"]
            request = youtube.playlistItems().list_next(request, response)
            if request is not None:
                response = await asyncio.to_thread(request.execute)

        return [
            Track(
                "https://www.youtube.com/watch?v="
                + item["snippet"]["resourceId"]["videoId"]
            )
            for item in playlist_items
        ]

    # ------------------------------------------------------------------
    # Tarefas de background
    # ------------------------------------------------------------------
    @tasks.loop(minutes=10.0)
    async def verifyalone(self):
        """Verifica se o bot esta sozinho e desconecta das guilds inativas."""
        log.info("Verificando se o bot está sozinho")

        for guild_id in list(self.players):
            state = self.players[guild_id]
            voice = state.voice
            if voice is None or voice.channel is None:
                continue

            humans = [m for m in voice.channel.members if not m.bot]
            if humans:
                log.info("%s : possui %s online", str(guild_id), str(len(humans)))
                continue

            log.info("Desconectando guild %s (ninguem no canal)", guild_id)
            async with state.lock:
                await self._disconnect_nolock(guild_id, state)

        if not any(state.voice for state in self.players.values()):
            log.info("Tarefa encerrada")
            self.verifyalone.cancel()  # pylint: disable=no-member

    @commands.command(hidden=True)
    async def equalizer(self, ctx: commands.Context, *args):
        """Configurações de equalizador.
        Modos: bass, normalize, earrape, ou vazio para desativar
        """
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        async with ctx.typing():
            if not args:
                state.equalizer = None
                state.volume = 50 / 100
            elif args[0] == "bass":
                state.equalizer = '-filter:a "bass=g=10:f=100:w=0.8"'
                state.volume = 50 / 100
            elif args[0] == "normalize":
                state.equalizer = "-filter:a loudnorm"
                state.volume = 50 / 100
            elif args[0] == "earrape":
                state.equalizer = '-filter:a "volume=20" -b:a 24k'
                state.volume = sys.float_info.max
            else:
                state.equalizer = None
                state.volume = 50 / 100

            if (
                state.voice
                and state.current
                and (state.voice.is_playing() or state.voice.is_paused())
            ):
                elapsed = int(time.monotonic() - state.started_at)
                async with state.lock:
                    try:
                        source = self._build_source(
                            state.current, state, extra_before=f"-ss {elapsed}"
                        )
                        state.voice._player.source = source
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        log.error("Erro ao aplicar equalizador: %s", e)

            if not args:
                return await ctx.send("Equalizador desativado")
            await ctx.send(f"Equalizador {args[0]} ativo")

    @commands.command(hidden=True)
    async def join(self, ctx: commands.Context, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        await channel.connect()

    async def randomizequeue(self, ctx: commands.Context):
        """Aleatoriza a ordem das proximas musicas (mantem a atual)."""
        state = self._state(ctx.guild.id)
        async with state.lock:
            random.shuffle(state.queue)
        await ctx.send("```Alterado a ordem da lista de musica```")

    async def tocar(self, ctx: commands.Context):
        """Garante que a fila da guild volte a tocar."""
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        async with state.lock:
            await self._advance_locked(ctx.guild.id, state)

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------
    @commands.command(aliases=["vol", "v", "volmax", "maxvol", "volmilas"])
    async def volume(self, ctx: commands.Context, *args):
        """Troca o volume.

        Args extra:
        -m para volume máximo.
        -r reseta volume padrão
        """
        self._state(ctx.guild.id).now_playing = None
        log.info("Alterando volume: %s", str(args))
        await self._change_volume(ctx, args, global_scope=False)

    @commands.command(aliases=["ff", "fastforward"])
    async def fast_forward(self, ctx: commands.Context, seconds: int):
        """Avança o áudio atual por um número específico de segundos.

        Sempre é considerado a partir do inicio do video.
        """
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        if not state.voice or not state.current:
            return
        if not (state.voice.is_playing() or state.voice.is_paused()):
            return
        async with state.lock:
            try:
                source = self._build_source(
                    state.current, state, extra_before=f"-ss {seconds}"
                )
                state.voice._player.source = source
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error("Erro no fast_forward: %s", e)

    @commands.command(
        aliases=["gvol", "gv", "gvolmax", "gmaxvol", "alwaysvolmax", "gvolmilas"]
    )
    async def globalvolume(self, ctx: commands.Context, *args):
        """Troca o volume global (persistente entre musicas)."""
        self._state(ctx.guild.id).now_playing = None
        log.info("Alterando volume global para: %s", str(args))
        await self._change_volume(ctx, args, global_scope=True)

    async def _parse_and_enqueue(self, ctx: commands.Context, url: str, args):
        """Monta as tracks a partir do input e adiciona na fila."""
        state = self._state(ctx.guild.id)
        front = "-f" in args
        repeat = 1
        for item in args:
            if item.startswith("-") and item[1:].isdigit():
                repeat = max(1, int(item[1:]))

        if not _is_url(url):
            words = [url] + [a for a in args if not a.startswith("-")]
            queries = [Track(" ".join(words), is_search=True)]
        elif re.search("spotify", url):
            queries = await self._spotify_tracks(url)
        elif re.search("playlist", url):
            queries = await self._youtube_playlist(url)
        else:
            queries = [Track(url)]

        tracks = []
        for query in queries:
            tracks.extend(Track(query.query, query.is_search) for _ in range(repeat))

        added = await self._enqueue(state, tracks, front)
        return added

    @commands.command(aliases=["paly", "ply", "p"])
    async def play(self, ctx: commands.Context, url: str, *args):
        """Toca a partir uma url ou pesquisa.

        Args opcionais:
        -shuffle - ordem aleatoria
        -n - numero de repetições
        """
        async with ctx.typing():
            self._state(ctx.guild.id).now_playing = None
            added = await self._parse_and_enqueue(ctx, url, args)

            if "-shuffle" in args:
                await self.randomizequeue(ctx)

        state = self._state(ctx.guild.id)
        if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
            log.info("Esta tocando, adicionando a queue")
            position = 1 if "-f" in args else len(state.queue) - 1
            await ctx.send(f"```Adicionado à fila, posição: {position}```")
        else:
            log.info("Nao esta tocando, comecando agora")
            if added == 0:
                await ctx.send("```Fila cheia```")
                return
            await self.tocar(ctx)

    @commands.command(aliases=["paus", "pau"])
    async def pause(self, ctx: commands.Context):
        """Pausa a música"""
        state = self._state(ctx.guild.id)
        if state.voice and state.voice.is_playing():
            if state.current and state.current.query == GARAGEM_TRACK_URL:
                state.volume = sys.float_info.max
                self._apply_volume(state)
                return await ctx.send("Lmao")
            state.voice.pause()
            await ctx.send(f"Pausado: `{state.current.title if state.current else ''}`")

    @commands.command(aliases=["res"])
    async def resume(self, ctx: commands.Context):
        """Retorna a tocar música"""
        state = self._state(ctx.guild.id)
        if state.voice and state.voice.is_paused():
            state.voice.resume()
            await ctx.send(f"Tocando: `{state.current.title if state.current else ''}`")

    @commands.command(aliases=["skup", "ski", "next", "skyp"])
    async def skip(self, ctx: commands.Context, quantidade=1):
        """Pula para o próximo item da lista de músicas.

        Args opcionais:
        quantidade - total de músicas para dar skip
        """
        try:
            quantidade = int(quantidade)
        except (TypeError, ValueError):
            quantidade = 1
        quantidade = max(quantidade, 1)

        state = self._state(ctx.guild.id)
        state.channel = ctx.channel

        if state.current and state.current.query == GARAGEM_TRACK_URL:
            state.volume = sys.float_info.max
            self._apply_volume(state)
            return await ctx.send("Lmao")

        async with state.lock:
            if quantidade > 1 and state.queue:
                del state.queue[: quantidade - 1]

            playing = state.voice and (
                state.voice.is_playing() or state.voice.is_paused()
            )
            if playing:
                log.info("Skip em %s", str(quantidade + 1))
                state.voice.stop()  # dispara _on_track_end
            elif state.queue:
                await self._advance_locked(ctx.guild.id, state)
            else:
                await ctx.send("`Não tem outras músicas na lista.`")

    @commands.command(aliases=["sto"])
    async def stop(self, ctx: commands.Context):
        """Desconecta o bot do canal de voz e limpa a lista de músicas"""
        state = self._state(ctx.guild.id)
        if state.current and state.current.query == GARAGEM_TRACK_URL:
            state.volume = sys.float_info.max
            self._apply_volume(state)
            return await ctx.send("Lmao")

        async with state.lock:
            await self._disconnect_nolock(ctx.guild.id, state)
        await ctx.send("`Parando de tocar...`")

    @commands.command(aliases=["list", "queue"])
    async def lista(self, ctx: commands.Context):
        """Exibe as 10 primeiras musicas da lista"""
        self._state(ctx.guild.id).now_playing = None
        state = self._state(ctx.guild.id)

        if not state.queue and not state.current:
            return await ctx.send("```Lista vazia```")

        async with ctx.typing():
            lista = "```"
            position = 1
            if state.current:
                lista += f"{position}: {state.current.display_name()}\n"
                position += 1
            for track in state.queue[: 10 - (position - 1)]:
                lista += f"{position}: {track.display_name()}\n"
                position += 1
            lista += "Tip: Quer tocar a musica 7? Use: mgy skip 6"
            lista += "```"
        await ctx.send(lista)

    @commands.command(aliases=["mash", "mas", "mashup", "rmash"])
    async def mashups(self, ctx: commands.Context, *args):
        """Toca mashups.

        Args:
        num - numero do mashup. Se usado com -r será o total de mashups à tocar
        -r - para random mashups
        """
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        log.info("Iniciando busca por mashups")

        try:
            mashups = _load_mashups()
        except OSError as e:
            log.error("Erro ao ler Dropbox.html: %s", e)
            return await ctx.send("```Lista de mashups indisponível```")

        num = "1"
        if not args:
            return await ctx.send(f"```{ctx.command.help}```")
        if args[0].isdigit() and int(args[0]) > 0:
            num = str(min(int(args[0]), MAX_QUEUE))

        if "-r" in args or "r" in args or "random" in args:
            log.info("Tocando %s aleatorios", num)
            count = min(int(num), len(mashups))
            choices = random.sample(mashups, count) if count else []
            tracks = [Track(link) for link in choices]
            found = bool(tracks)
        else:
            found = False
            tracks = []
            for link in mashups[:MASHUP_SCAN_LIMIT]:
                try:
                    info = await _extract_info_isolated(link)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    log.warning("Erro ao buscar mashup '%s': %s", link, exc)
                    continue
                nome = info.get("title") if info else None
                if nome and nome.startswith(num):
                    log.info("Encontrou: %s", nome)
                    tracks = [Track(link)]
                    found = True
                    break

        if not found:
            log.info("Mashup numero %s nao encontrado", num)
            return await ctx.send("```Não encontrado```")

        await self._enqueue(state, tracks, front=False)
        if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
            await ctx.send(
                f"```Adicionado {num} à lista. Total na lista: {len(state.queue)}```"
            )
        else:
            await self.tocar(ctx)

    @commands.command(aliases=["clear", "limpa", "clean"])
    async def limpar(self, ctx: commands.Context):
        """Limpa a lista de musicas (mantém a música atual)"""
        state = self._state(ctx.guild.id)
        async with state.lock:
            state.queue.clear()
        await ctx.send("```Lista limpa```")

    @commands.command(aliases=["random", "randomize", "shuff"])
    async def shuffle(self, ctx: commands.Context):
        """Da uma shuffle na lista de musica"""
        await self.randomizequeue(ctx)

    @commands.command(aliases=["dk", "donkey", "kong", "bonus"])
    async def sdk(self, ctx: commands.Context, quantidade=5):
        """Shuffle 'n' donkey kong"""
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        try:
            quan = abs(int(quantidade))
        except (TypeError, ValueError):
            quan = 5
        quan = min(quan, MAX_QUEUE)

        tracks = [Track(BONUS_ROOM_URL) for _ in range(quan)]
        await self._enqueue(state, tracks, front=False)
        await self.randomizequeue(ctx)

        if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
            await ctx.send(
                f"```Adicionado {quan} Bonus Room à lista. Total na lista: {len(state.queue)}```"
            )
        else:
            await self.tocar(ctx)

    @commands.command(aliases=["t", "tocar"])
    async def toca(self, ctx: commands.Context, name: str, *args):
        """Toca link salvo.

        Verifique os links com: mgy mlinks.
        Args:
        -n - Numero de repetições
        -shuffle - Ordem aleatória

        Exemplo: mgy t garagem -24 -shuffle
        """
        resultado = await self.pg.aquery(
            "select * from MUSIC_LINKS WHERE NAME LIKE %s", (f"{name}%",)
        )

        if not resultado:
            await ctx.send(
                "Nome não encontrado. Você pode verificar os links existentes com: mgy musiclinks"
            )
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            return

        url = resultado[0]["url"]
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        await self._parse_and_enqueue(ctx, url, args)

        if "-shuffle" in args:
            await self.randomizequeue(ctx)

        if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
            await ctx.send(
                f"```Adicionado {resultado[0]['name']} à lista. Total na lista: {len(state.queue)}```"
            )
        else:
            await self.tocar(ctx)

    @commands.command()
    async def add(self, ctx: commands.Context, name: str, url: str):
        """Cria comando para tocar uma musica.

        Usado em conjunto com o comando 'tocar'.
        Exemplo: mgy add garagem link. Em seguida utilize: mgy t garagem"""
        async with ctx.typing():
            if len(name) > 20:
                return await ctx.send("Nome muito longo, use até 20 caracteres")

            resultado = await self.pg.aquery(
                "select * from MUSIC_LINKS WHERE NAME = %s", (name,)
            )
            if resultado:
                return await ctx.send(
                    "Nome já existe. Você pode verificar os links existentes com: mgy musiclinks"
                )

            if not _is_url(url):
                return await ctx.send("Url invalida")

            usuarios = await self.pg.aquery(
                "select ID_USUARIOS from USUARIOS WHERE USER_ID_DISCORD = %s",
                (str(ctx.author.id),),
            )
            if not usuarios:
                return await ctx.send("Usuário não cadastrado")

            titulo = " "
            try:
                info = await _extract_info_isolated(url)
                if info and info.get("title"):
                    titulo = info["title"]
            except Exception as exc:  # pylint: disable=broad-exception-caught
                log.warning("Erro ao buscar título de '%s': %s", url, exc)

            await self.pg.aupdate(
                "insert into MUSIC_LINKS (NAME, URL, USER_ID, TITLE)"
                " values (%s, %s, %s, %s)",
                (name, url, str(usuarios[0]["id_usuarios"]), titulo),
            )
            await ctx.send(f"Adicionado {name}. Para tocar use: mgy t {name}")

    @commands.command(aliases=["mlist", "mlinks", "links"])
    async def musiclinks(self, ctx: commands.Context):
        """Mostra os comandos de musica criados"""
        async with ctx.typing():
            resultado = await self.pg.aquery("select * from MUSIC_LINKS")
            if not resultado:
                return

            embeds = []
            name = ""
            title = ""
            for i, x in enumerate(resultado):
                name += f"[{x['name']}]({x['url']})\n"
                title += f"{x['title'] if x['title'] else 'Não encontrado'}\n"

                if i != 0 and i % 10 == 0:
                    embed = discord.Embed(colour=0xFA00D4)
                    embed.add_field(name="Nome", value=name, inline=True)
                    embed.add_field(name="Titulo", value=title, inline=True)
                    embeds.append(embed)
                    name = ""
                    title = ""

            embed = discord.Embed(colour=0xFA00D4)
            if name:
                embed.add_field(name="Nome", value=name, inline=True)
                embed.add_field(name="Titulo", value=title, inline=True)
            embed.set_footer(
                text="Para tocar use: mgy t nome. Com nome sendo um dos mostrados acima, use -shuffle para shuffle",
                icon_url=AVATAR_URL,
            )
            embeds.append(embed)

            for embed in embeds:
                await ctx.send(embed=embed)

    @play.before_invoke
    @mashups.before_invoke
    @sdk.before_invoke
    @toca.before_invoke
    async def ensure_voice(self, ctx: commands.Context):
        """Garante que o bot esta conectado e que o estado da guild existe."""
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        state.now_playing = None

        if state.voice is None:
            if ctx.author.voice:
                state.voice = await ctx.author.voice.channel.connect()
                try:
                    if not self.verifyalone.is_running():  # pylint: disable=no-member
                        self.verifyalone.start()  # pylint: disable=no-member
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error("Erro ao iniciar tarefa em background: %s", e)
            else:
                log.warning("Autor nao conectado no canal de voz")
                await ctx.send("Você não está conectado em um canal de voz")
                raise commands.CommandError("Author not connected to a voice channel.")


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Music(bot))
