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
# Timeout por inatividade: se o yt-dlp ficar sem emitir nenhuma linha por esse
# tempo, consideramos que travou e o processo e morto. Enquanto ele continua
# progredindo (imprimindo linhas de log), o contador reinicia.
YTDLP_IDLE_TIMEOUT_SECONDS = 60
# Teto absoluto de seguranca, mesmo que o yt-dlp continue imprimindo saida.
YTDLP_MAX_TIMEOUT_SECONDS = 900
# Intervalo de checagem do yt-dlp: curto para reagir rapido a skip/stop
# (abort) e para medir a inatividade com precisao.
YTDLP_POLL_INTERVAL_SECONDS = 1.0
# Reconexao de voz: quantas tentativas e quanto esperar entre elas.
VOICE_CONNECT_ATTEMPTS = 3
VOICE_RECONNECT_DELAY_SECONDS = 2.0
MAX_RESOLVE_ATTEMPTS = 10
MASHUP_SCAN_LIMIT = 100
# Validade das stream URLs: lemos o vencimento exato do campo "expire" que o
# proprio googlevideo embute na URL. A idade maxima so e usada como fallback
# quando a URL nao expoe o vencimento.
YTDLP_URL_EXPIRY_MARGIN_SECONDS = 120
YTDLP_URL_MAX_AGE_SECONDS = 4 * 60 * 60
# Se o player terminar com erro logo no comeco, a URL provavelmente expirou:
# tenta UMA re-resolucao da mesma faixa antes de pular para a proxima.
PLAYBACK_START_THRESHOLD_SECONDS = 8
PLAYBACK_MAX_RETRIES = 1

# Define YTDLP_DEBUG=1 no ambiente para incluir tambem as linhas [debug]
# do yt-dlp no log (o --verbose ja e sempre usado para manter o stdout limpo)
YTDLP_DEBUG = os.environ.get("YTDLP_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

COOKIES_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
)
DROPBOX_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Dropbox.html")
)

log = logging.getLogger("music")


class ResolutionAborted(Exception):
    """Levantada quando skip/stop cancela uma resolucao yt-dlp em andamento."""


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

YOUTUBE_PLAYER_CLIENTS = ["web_embedded", "web"]

YTDLP_JS_RUNTIMES = [
    runtime.strip()
    for runtime in os.environ.get("YTDLP_JS_RUNTIMES", "").split(",")
    if runtime.strip()
]

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
    "before_options": "-nostdin -hide_banner -loglevel error -re -probesize 32k -analyzeduration 0 -rw_timeout 15000000 -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_max_retries 3",
    "options": "-vn -sn -dn -threads 1 -filter_threads 1 -filter_complex_threads 1 -nostats",
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
    # Instante (time.monotonic) em que a faixa foi resolvida; fallback de
    # validade quando a URL nao traz "expire".
    resolved_at: float | None = None
    # Quantas vezes essa faixa ja foi re-resolvida por falha ao comecar.
    retries: int = 0

    def display_name(self) -> str:
        """Nome para exibir em listas, sem resolver novamente."""
        return self.title or self.query


@dataclass
class GuildPlayer:
    """Estado de reproducao independente de cada guild."""

    queue: list[Track] = field(default_factory=list)
    current: Track | None = None
    voice: discord.VoiceClient | None = None
    voice_channel: discord.VoiceChannel | None = None
    channel: discord.abc.Messageable | None = None
    now_playing: discord.Message | None = None
    volume: float = 0.5
    equalizer: str | None = None
    started_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    prefetch_task: asyncio.Task | None = None
    # Sinaliza para uma resolucao yt-dlp em andamento que ela deve parar
    # (setado por skip/stop; limpo quando um novo avanco comeca).
    abort_event: asyncio.Event = field(default_factory=asyncio.Event)
    # True enquanto _advance_locked esta resolvendo uma faixa (yt-dlp).
    resolving: bool = False
    # True enquanto uma reconexao de voz esta em andamento.
    reconnecting: bool = False
    # Task de reconexao (mantida viva para nao ser coletada pelo GC).
    reconnect_task: asyncio.Task | None = None
    # Identifica o player atual; callbacks "after" antigos sao descartados.
    play_generation: int = 0


def _url_expires_at(url: str) -> float | None:
    """Epoch (s) em que a URL expira, lendo o campo 'expire' da query string.

    As URLs diretas do googlevideo (e manifests) embutem "expire=<epoch>" no
    query string. Raramente o valor vem em milissegundos; normaliza aqui.
    Retorna None quando nao e possivel saber o vencimento.
    """
    values = parse_qs(urlparse(url).query).get("expire")
    if not values:
        return None
    try:
        value = float(values[-1])
    except (TypeError, ValueError):
        return None
    if value > 1e12:  # parece milissegundos
        value /= 1000.0
    return value


def _is_track_fresh(track: Track) -> bool:
    """True se o stream_url ainda e confiavel para tocar.

    Usa o vencimento exato embutido na URL ('expire') com uma pequena margem
    de seguranca. Sem o campo, cai para a idade maxima baseada em resolved_at.
    """
    if not track.stream_url:
        return False
    expires = _url_expires_at(track.stream_url)
    if expires is not None:
        return time.time() + YTDLP_URL_EXPIRY_MARGIN_SECONDS < expires
    return (
        track.resolved_at is not None
        and time.monotonic() - track.resolved_at <= YTDLP_URL_MAX_AGE_SECONDS
    )


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


async def _extract_info_isolated(
    url: str,
    idle_timeout: float = YTDLP_IDLE_TIMEOUT_SECONDS,
    max_timeout: float | None = YTDLP_MAX_TIMEOUT_SECONDS,
    abort_event: asyncio.Event | None = None,
) -> dict:
    """Extrai metadados em um subprocesso que pode ser morto sem travar o bot.

    O timeout e por inatividade: o processo so e morto se ficar ``idle_timeout``
    segundos sem emitir nenhuma linha de log. Enquanto ele continua progredindo
    o cronometro reinicia, permitindo extracoes lentas mas vivas. ``max_timeout``
    e um teto absoluto de seguranca (``None`` desativa).

    Se ``abort_event`` for setado (por skip/stop), o subprocesso e morto e
    :class:`ResolutionAborted` e levantada.

    --verbose e sempre usado para forcar o yt-dlp a enviar as mensagens para
    o stderr, deixando o stdout apenas com o JSON (sem --quiet o yt-dlp
    misturaria as mensagens no stdout e corromperia o JSON). As linhas
    [debug] sao filtradas a menos que YTDLP_DEBUG esteja definido.
    """
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
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
        "--verbose",
    ]
    if os.path.exists(COOKIES_FILE):
        command.extend(["--cookies", COOKIES_FILE])
    if YTDLP_JS_RUNTIMES:
        command.append("--no-js-runtimes")
        for runtime in YTDLP_JS_RUNTIMES:
            command.extend(["--js-runtimes", runtime])
    command.append(url)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=1024 * 1024,
    )

    stdout_chunks: list[bytes] = []
    stderr_lines: list[str] = []
    last_activity = time.monotonic()

    async def _drain_stdout(stream):
        # Le em blocos: o JSON de --dump-single-json e uma unica linha enorme,
        # entao readline() estouraria o limite do StreamReader.
        nonlocal last_activity
        if stream is None:
            return
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            stdout_chunks.append(chunk)
            last_activity = time.monotonic()

    async def _drain_stderr(stream):
        nonlocal last_activity
        if stream is None:
            return
        while True:
            raw = await stream.readline()
            if not raw:
                break
            last_activity = time.monotonic()
            line = raw.decode(errors="replace").rstrip()
            if not line:
                continue
            stderr_lines.append(line)
            # Filtra as linhas [debug] do --verbose a menos que YTDLP_DEBUG
            if line.startswith("[debug]") and not YTDLP_DEBUG:
                log.debug("yt-dlp [%s] %s", url, line)
            else:
                log.info("yt-dlp [%s] %s", url, line)

    stdout_task = asyncio.create_task(_drain_stdout(process.stdout))
    stderr_task = asyncio.create_task(_drain_stderr(process.stderr))
    wait_task = asyncio.create_task(process.wait())

    def _stderr_tail(limit: int = 50) -> str:
        return "\n".join(stderr_lines[-limit:]) or "(sem saida do yt-dlp)"

    timeout_reason: str | None = None
    aborted = False
    try:
        started = time.monotonic()
        while True:
            if abort_event is not None and abort_event.is_set():
                aborted = True
                break

            now = time.monotonic()
            idle_left = idle_timeout - (now - last_activity)
            if idle_left <= 0:
                timeout_reason = f"sem saida por {idle_timeout:.0f}s"
                break

            wait_budget = min(idle_left, YTDLP_POLL_INTERVAL_SECONDS)
            if max_timeout is not None:
                max_left = max_timeout - (now - started)
                if max_left <= 0:
                    timeout_reason = f"tempo maximo de {max_timeout:.0f}s"
                    break
                wait_budget = min(wait_budget, max_left)

            try:
                await asyncio.wait_for(asyncio.shield(wait_task), timeout=wait_budget)
                break
            except TimeoutError:
                # Sem saida dentro da janela: reavalia progresso/abort.
                continue
    except asyncio.CancelledError:
        process.kill()
        wait_task.cancel()
        stdout_task.cancel()
        stderr_task.cancel()
        raise

    if aborted:
        process.kill()
        await wait_task
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        log.info("yt-dlp abortado para %s. Ultimas linhas:\n%s", url, _stderr_tail(10))
        raise ResolutionAborted(url)

    if timeout_reason is not None:
        process.kill()
        await wait_task
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        log.error(
            "yt-dlp timed out (%s) for %s. Ultimas linhas:\n%s",
            timeout_reason,
            url,
            _stderr_tail(),
        )
        raise TimeoutError(f"yt-dlp extraction timed out ({timeout_reason})")

    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
    stdout = b"".join(stdout_chunks)

    if process.returncode != 0:
        error = _stderr_tail()
        log.error(
            "yt-dlp exited with %s for %s. Ultimas linhas:\n%s",
            process.returncode,
            url,
            error,
        )
        raise RuntimeError(error or f"yt-dlp exited with {process.returncode}")

    try:
        return json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raw = stdout.decode(errors="replace")
        log.error(
            "yt-dlp returned invalid JSON for %s (%d bytes de stdout):\n%s",
            url,
            len(raw),
            raw[:2000],
        )
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

    async def _resolve_track(
        self,
        track: Track,
        idle_timeout: float = YTDLP_IDLE_TIMEOUT_SECONDS,
        max_timeout: float | None = YTDLP_MAX_TIMEOUT_SECONDS,
        abort_event: asyncio.Event | None = None,
    ) -> Track | None:
        """Resolve uma Track via yt-dlp. Retorna None em caso de falha."""
        if _is_track_fresh(track):
            return track
        if track.stream_url:
            log.info("Stream URL de '%s' expirou; resolvendo novamente", track.query)
            track.stream_url = None

        started_at = time.monotonic()
        try:
            data = await _extract_info_isolated(
                track.query, idle_timeout, max_timeout, abort_event
            )
        except ResolutionAborted:
            raise
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
        track.resolved_at = time.monotonic()

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
        self._cancel_prefetch(state)
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

    def _sync_voice(self, state: GuildPlayer, guild: discord.Guild) -> bool:
        """Sincroniza state.voice com a conexao real, descartando fantasmas.

        O discord.py pode remover o voice client da guild sem que o nosso
        estado saiba (instancia "fantasma"): state.voice continua preenchido
        mas nao ha conexao. Aqui detectamos isso e adotamos o cliente real.
        Retorna True se ha uma conexao valida.
        """
        voice = state.voice
        if voice is not None and not voice.is_connected():
            log.warning("Voice client fantasma descartado (guild=%s)", guild.id)
            state.voice = None

        guild_voice = guild.voice_client
        if guild_voice is not None and guild_voice.is_connected():
            state.voice = guild_voice
            state.voice_channel = guild_voice.channel or state.voice_channel
            return True

        return state.voice is not None and state.voice.is_connected()

    async def _connect_channel(
        self, state: GuildPlayer, channel: discord.VoiceChannel
    ) -> bool:
        """Conecta o bot ao canal, com algumas tentativas. True em sucesso."""
        for attempt in range(1, VOICE_CONNECT_ATTEMPTS + 1):
            try:
                state.voice = await channel.connect()
                state.voice_channel = channel
                log.info("Conectado ao canal '%s' (tentativa %d)", channel, attempt)
                return True
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(
                    "Falha ao conectar em '%s' (tentativa %d): %s",
                    channel,
                    attempt,
                    e,
                    exc_info=True,
                )
                if attempt < VOICE_CONNECT_ATTEMPTS:
                    await asyncio.sleep(VOICE_RECONNECT_DELAY_SECONDS)
        return False

    async def _reconnect_voice(self, guild_id: int, channel: discord.VoiceChannel | None):
        """Tenta voltar ao canal apos uma queda e retomar a fila."""
        state = self._state(guild_id)
        try:
            if channel is None:
                return
            for attempt in range(1, VOICE_CONNECT_ATTEMPTS + 1):
                # Alguem ja reconectou ou um stop limpou tudo nesse meio tempo.
                if state.voice is not None and state.voice.is_connected():
                    return
                if state.current is None and not state.queue:
                    return

                await asyncio.sleep(VOICE_RECONNECT_DELAY_SECONDS)
                if not await self._connect_channel(state, channel):
                    continue

                log.info("Reconectado ao canal '%s' (guild=%s)", channel, guild_id)
                async with state.lock:
                    if state.current is not None and not (
                        state.voice.is_playing() or state.voice.is_paused()
                    ):
                        # A faixa que estava no ar se perdeu: recoloca na frente.
                        state.queue.insert(0, state.current)
                        state.current = None
                    await self._advance_locked(guild_id, state)
                return
            log.error("Nao consegui reconectar ao canal (guild=%s)", guild_id)
        finally:
            state.reconnecting = False

    def _schedule_reconnect(self, guild_id: int, channel: discord.VoiceChannel | None):
        """Agenda uma reconexao, evitando tarefas duplicadas."""
        state = self._state(guild_id)
        if channel is None:
            return
        task = state.reconnect_task
        if task is not None and not task.done():
            return
        state.reconnecting = True
        state.reconnect_task = asyncio.create_task(
            self._reconnect_voice(guild_id, channel)
        )

    def _cancel_prefetch(self, state: GuildPlayer):
        """Cancela a resolucao antecipada em andamento, se houver."""
        task = state.prefetch_task
        state.prefetch_task = None
        if task is not None and not task.done():
            task.cancel()

    def _abort_resolution(self, state: GuildPlayer) -> bool:
        """Pede para a resolucao yt-dlp em andamento parar, sem esperar o lock.

        Retorna True se havia uma resolucao em andamento (para o chamador
        decidir o que fazer com a faixa que foi descartada).
        """
        was_resolving = state.resolving
        state.abort_event.set()
        self._cancel_prefetch(state)
        return was_resolving

    def _schedule_prefetch(self, guild_id: int, state: GuildPlayer):
        """Resolve a proxima faixa em segundo plano para esconder a latencia."""
        self._cancel_prefetch(state)
        if not state.queue or _is_track_fresh(state.queue[0]):
            return
        state.prefetch_task = asyncio.create_task(self._prefetch_next(guild_id, state))

    async def _prefetch_next(self, guild_id: int, state: GuildPlayer):
        """Resolve a proxima faixa da fila (mutando o proprio objeto da fila)."""
        if not state.queue:
            return
        track = state.queue[0]
        if _is_track_fresh(track):
            return
        try:
            resolved = await self._resolve_track(track)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.debug("Prefetch falhou para %s: %s", track.query, e)
            return
        if resolved is not None:
            log.info("Prefetch pronto: %s", resolved.display_name())

    async def _advance_locked(self, guild_id: int, state: GuildPlayer):
        """Toca a proxima faixa valida. Deve ser chamado com o lock adquirido."""
        self._cancel_prefetch(state)
        state.abort_event.clear()
        if state.current is not None or state.voice is None:
            return

        attempts = 0
        while state.queue and attempts < MAX_RESOLVE_ATTEMPTS:
            attempts += 1
            track = state.queue.pop(0)
            state.resolving = True
            try:
                resolved = await self._resolve_track(
                    track, abort_event=state.abort_event
                )
            except ResolutionAborted:
                log.info("Resolucao de '%s' abortada (skip/stop)", track.query)
                return
            finally:
                state.resolving = False
            if resolved is None:
                continue

            try:
                source = self._build_source(resolved, state)
            except Exception as e:
                log.error("Erro ao criar FFmpeg Audio para %s: %s", track.query, e)
                await asyncio.sleep(0.5)
                continue

            state.current = resolved
            state.started_at = time.monotonic()
            state.play_generation += 1
            generation = state.play_generation
            try:
                state.voice.play(source, after=self._make_after(guild_id, generation))
            except Exception as e:
                log.error("Erro ao tocar %s: %s", track.query, e)
                state.current = None
                await asyncio.sleep(1)
                continue

            self._apply_volume(state)
            log.info("Tocando %s", resolved.title)
            if resolved.title == BONUS_ROOM_TITLE:
                asyncio.create_task(self._enable_double_xp())
            await self._announce_locked(guild_id, state, resolved)
            self._schedule_prefetch(guild_id, state)
            return

        if state.queue:
            log.warning(
                "Nao consegui resolver %d faixas seguidas; pausando a fila (%d restantes).",
                MAX_RESOLVE_ATTEMPTS,
                len(state.queue),
            )
            return
        await self._disconnect_nolock(guild_id, state)


    def _make_after(self, guild_id: int, generation: int):
        def after(error):
            if error:
                log.error("Player da guild %s terminou com erro: %s", guild_id, error)
            asyncio.run_coroutine_threadsafe(
                self._on_track_end(guild_id, generation, error), self.bot.loop
            )

        return after

    async def _on_track_end(
        self, guild_id: int, generation: int | None = None, error=None
    ):
        """Avanca a fila quando uma musica termina (unico cleanup automatico).

        ``generation`` identifica o player que disparou o callback. Callbacks
        obsoletos (de uma conexao que caiu, por exemplo) sao ignorados para nao
        interromper a faixa que acabou de comecar apos uma reconexao.

        Se o player terminar com erro logo no comeco (antes de
        PLAYBACK_START_THRESHOLD_SECONDS), a URL provavelmente expirou: tenta-se
        UMA re-resolucao da mesma faixa antes de avancar para a proxima.
        """
        state = self._state(guild_id)
        async with state.lock:
            if generation is not None and generation != state.play_generation:
                log.debug(
                    "Ignorando after obsoleto da guild %s (gen %s != %s)",
                    guild_id,
                    generation,
                    state.play_generation,
                )
                return
            failed = state.current
            if error is not None and failed is not None:
                elapsed = (
                    time.monotonic() - state.started_at if state.started_at else 0.0
                )
                if (
                    elapsed < PLAYBACK_START_THRESHOLD_SECONDS
                    and failed.retries < PLAYBACK_MAX_RETRIES
                ):
                    log.warning(
                        "Faixa '%s' falhou ao comecar (%.1fs, %s); re-resolvendo (guild=%s)",
                        failed.query,
                        elapsed,
                        error,
                        guild_id,
                    )
                    failed.retries += 1
                    failed.stream_url = None
                    failed.resolved_at = None
                    state.queue.insert(0, failed)
                    state.current = None
                    await self._advance_locked(guild_id, state)
                    return
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
            if voice is None:
                continue
            if not voice.is_connected():
                log.warning(
                    "Voice client fantasma detectado (guild=%s); tentando recuperar",
                    guild_id,
                )
                state.voice = None
                if state.current is not None or state.queue:
                    self._schedule_reconnect(guild_id, state.voice_channel)
                continue
            if voice.channel is None:
                continue

            humans = [m for m in voice.channel.members if not m.bot]
            if humans:
                log.info("%s : possui %s online", str(guild_id), str(len(humans)))
                continue

            log.info("Desconectando guild %s (ninguem no canal)", guild_id)
            async with state.lock:
                await self._disconnect_nolock(guild_id, state)

        if not any(
            state.voice or state.reconnecting for state in self.players.values()
        ):
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
        state = self._state(ctx.guild.id)
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
            state.voice = ctx.voice_client
        else:
            state.voice = await channel.connect()
        state.voice_channel = channel

    async def randomizequeue(self, ctx: commands.Context):
        """Aleatoriza a ordem das proximas musicas (mantem a atual)."""
        state = self._state(ctx.guild.id)
        async with state.lock:
            self._cancel_prefetch(state)
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
        state = self._state(ctx.guild.id)
        async with ctx.typing():
            state.now_playing = None
            added = await self._parse_and_enqueue(ctx, url, args)

            if "-shuffle" in args:
                await self.randomizequeue(ctx)

            if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
                log.info("Esta tocando, adicionando a queue")
                position = 1 if "-f" in args else len(state.queue) - 1
                await ctx.send(f"```Adicionado à fila, posição: {position}```")
            else:
                log.info("Nao esta tocando, comecando agora")
                if added == 0:
                    await ctx.send("```Fila cheia```")
                    return
                # A resolucao da primeira faixa (yt-dlp) acontece dentro do
                # typing para o usuario ver que o bot ainda esta trabalhando.
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
        elif state.voice and state.voice.is_paused():
            await ctx.send("`Já está pausado.`")
        else:
            await ctx.send("`Nada tocando para pausar.`")

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

        # Aborta sem esperar o lock: se o yt-dlp estiver resolvendo uma faixa,
        # ele para na hora em vez de travar o comando por ate 60s.
        aborting = self._abort_resolution(state)

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
            elif aborting:
                # A unica faixa em andamento era a que foi abortada.
                await self._disconnect_nolock(ctx.guild.id, state)
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

        # Aborta uma resolucao yt-dlp em andamento antes de pegar o lock.
        self._abort_resolution(state)

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
            self._cancel_prefetch(state)
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
        async with ctx.typing():
            await self._enqueue(state, tracks, front=False)
            await self.randomizequeue(ctx)

            if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
                await ctx.send(
                    f"```Adicionado {quan} Bonus Room à lista. Total na lista: {len(state.queue)}```"
                )
            else:
                # A resolucao da primeira faixa fica dentro do typing.
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
        async with ctx.typing():
            await self._parse_and_enqueue(ctx, url, args)

            if "-shuffle" in args:
                await self.randomizequeue(ctx)

            if state.voice and (state.voice.is_playing() or state.voice.is_paused()):
                await ctx.send(
                    f"```Adicionado {resultado[0]['name']} à lista. Total na lista: {len(state.queue)}```"
                )
            else:
                # A resolucao da primeira faixa fica dentro do typing.
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

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Detecta quedas/mudancas de canal do bot e reage.

        O discord.py pode perder a conexao de voz sem que o nosso estado saiba
        (instancia "fantasma"). Se o bot saiu do canal com fila/musica em
        andamento, tentamos voltar automaticamente; caso contrario apenas
        limpamos o estado para o proximo comando reconectar.
        """
        if self.bot.user is None or member.id != self.bot.user.id:
            return
        state = self.players.get(member.guild.id)
        if state is None:
            return

        if after.channel is not None:
            # (Re)conectou ou foi movido: mantem o estado alinhado.
            state.voice_channel = after.channel
            current = member.guild.voice_client
            if current is not None and current.is_connected():
                state.voice = current
            return

        # after.channel is None -> o bot saiu / foi desconectado.
        log.warning(
            "Bot saiu do canal de voz (guild=%s, canal=%s)",
            member.guild.id,
            before.channel,
        )
        state.voice = None
        left_channel = state.voice_channel or before.channel
        if (state.current is None and not state.queue) or left_channel is None:
            return
        self._schedule_reconnect(member.guild.id, left_channel)

    @play.before_invoke
    @mashups.before_invoke
    @sdk.before_invoke
    @toca.before_invoke
    async def ensure_voice(self, ctx: commands.Context):
        """Garante que o bot esta conectado e que o estado da guild existe."""
        state = self._state(ctx.guild.id)
        state.channel = ctx.channel
        state.now_playing = None

        # Conexao ja valida (inclusive movida por fora): nada a fazer.
        if self._sync_voice(state, ctx.guild):
            return

        if not ctx.author.voice:
            log.warning("Autor nao conectado no canal de voz")
            await ctx.send("Você não está conectado em um canal de voz")
            raise commands.CommandError("Author not connected to a voice channel.")

        channel = ctx.author.voice.channel
        log.info(
            "ensure_voice: conectando em '%s' (guild=%s, dpy_voice_client=%s)",
            channel,
            ctx.guild.id,
            ctx.voice_client,
        )
        started = time.monotonic()
        if not await self._connect_channel(state, channel):
            await ctx.send("Não consegui conectar ao canal de voz. Tente novamente.")
            raise commands.CommandError("Failed to connect to voice channel.")
        log.info("ensure_voice: conectado em %.1fs", time.monotonic() - started)

        try:
            if not self.verifyalone.is_running():  # pylint: disable=no-member
                self.verifyalone.start()  # pylint: disable=no-member
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error("Erro ao iniciar tarefa em background: %s", e)


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Music(bot))
