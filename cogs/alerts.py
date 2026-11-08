"""
Modulo de alertas: aniversarios dos usuarios, lives na Twitch e videos novos
no YouTube. Os links ficam na tabela USUARIOS (colunas twitch/youtube).
"""

import logging
import os
import time
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
import discord
from discord.ext import commands, tasks

from utils.pgdatabase import Postgres

log = logging.getLogger("Alertas")

try:
    TZ_BRASIL = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:  # pragma: no cover - fallback para ambientes sem tzdata
    from datetime import timedelta, timezone

    TZ_BRASIL = timezone(timedelta(hours=-3))

BIRTHDAY_INTERVAL_MIN = 30
TWITCH_INTERVAL_MIN = 10
YOUTUBE_INTERVAL_MIN = 60

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"

YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YOUTUBE_PLACEHOLDER_KEY = "youtubeHere"


def parse_birthday(text: str):
    """Converte 'DD/MM', 'DD-MM' ou 'DD/MM/YYYY' em date, ou None se invalido."""
    if not text:
        return None
    parts = text.strip().replace("-", "/").split("/")
    try:
        if len(parts) == 2:
            day, month = (int(part) for part in parts)
            year = 2000
        elif len(parts) == 3:
            day, month, year = (int(part) for part in parts)
        else:
            return None
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def twitch_username(url: str):
    """Extrai o nome de usuario de um link da Twitch."""
    if not url:
        return None
    path = urlparse(url.strip()).path.strip("/")
    return path.split("/")[0].lower() if path else None


def youtube_channel_ref(url: str):
    """Devolve (tipo, valor) para localizar um canal do YouTube, ou None.

    Tipos: 'channel' (id direto), 'user' (forUsername) ou 'handle' (@handle).
    """
    if not url:
        return None
    path = urlparse(url.strip()).path.strip("/")
    parts = path.split("/")
    if not path or not parts or not parts[0]:
        return None
    first = parts[0]
    if first == "channel" and len(parts) >= 2:
        return ("channel", parts[1])
    if first == "user" and len(parts) >= 2:
        return ("user", parts[1])
    if first.startswith("@") and len(first) > 1:
        return ("handle", first)
    return None


class Alerts(commands.Cog, name="Alerts"):
    """Alertas de aniversarios e transmissões/videos dos usuarios"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            self.pg = Postgres()
        except Exception as error:  # noqa: BLE001
            log.error("Banco de dados indisponivel: %s", error)
            self.pg = None

        self._loops_started = False
        self._last_birthday_date = None

        self._twitch_token = None
        self._twitch_token_expires = 0.0
        self._twitch_status = {}
        self._twitch_initialized = False

        self._youtube_latest = {}

        self._session: aiohttp.ClientSession | None = None

    async def cog_unload(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _find_user(self, discord_id: int, guild_id: int):
        """Busca a linha do usuario no servidor."""
        if not self.pg:
            return None
        sql = (
            "SELECT * FROM USUARIOS u, SERVIDORES s"
            " WHERE u.USER_ID_DISCORD = %s"
            " AND s.NUMERO_ID_SERVIDOR = %s"
            " AND u.SERVIDOR_ID = s.ID_SERVIDORES"
        )
        return await self.pg.aquery(sql, (str(discord_id), str(guild_id))) or None

    async def _get_alert_channel(
        self, guild: discord.Guild, alert_channel_id
    ) -> discord.abc.Messageable:
        """Resolve o canal de alertas, com fallback para o canal do sistema."""
        channel = None
        if alert_channel_id:
            channel = guild.get_channel(int(alert_channel_id))
        if channel is None:
            channel = guild.system_channel
        if channel is None and guild.text_channels:
            channel = guild.text_channels[0]
        return channel

    async def _send_alert(self, guild_id, alert_channel_id, text: str):
        """Envia um alerta no canal configurado do servidor."""
        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            return
        channel = await self._get_alert_channel(guild, alert_channel_id)
        if channel is None:
            log.warning("Sem canal de alertas para o servidor %s", guild_id)
            return
        try:
            await channel.send(text)
        except discord.HTTPException as error:
            log.error("Erro ao enviar alerta no servidor %s: %s", guild_id, error)

    # ------------------------------------------------------------------ #
    # Comandos
    # ------------------------------------------------------------------ #
    @commands.command(name="birthday")
    async def birthday(self, ctx: commands.Context, *, data: str | None = None):
        """Define ou mostra seu aniversario. Uso: mgy birthday DD/MM"""
        if not self.pg:
            return await ctx.send("Banco de dados indisponivel.")
        resultado = await self._find_user(ctx.author.id, ctx.guild.id)
        if not resultado:
            return await ctx.send(
                "Usuario nao encontrado. Mande uma mensagem no servidor primeiro."
            )

        if data is None:
            atual = resultado[0]["birthday"]
            if atual:
                return await ctx.send(f"Seu aniversario esta registrado: {atual:%d/%m}.")
            return await ctx.send(
                "Voce ainda nao definiu seu aniversario. Use: mgy birthday DD/MM"
            )

        birthday = parse_birthday(data)
        if not birthday:
            return await ctx.send("Data invalida. Use o formato DD/MM (ex: 25/12).")

        sql = (
            "UPDATE USUARIOS SET birthday = %s WHERE ID_USUARIOS = %s"
        )
        if await self.pg.aupdate(sql, (birthday, resultado[0]["id_usuarios"])):
            await ctx.send(f"Aniversario registrado: {birthday:%d/%m}!")
        else:
            await ctx.send("Ocorreu um erro ao registrar o aniversario.")

    @commands.command(name="alertchannel")
    @commands.has_role("Staff")
    async def alertchannel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """Define o canal onde o bot envia os alertas. Staff only"""
        if not self.pg:
            return await ctx.send("Banco de dados indisponivel.")
        channel = channel or ctx.channel
        resultado = await self.pg.aquery(
            "SELECT * FROM SERVIDORES WHERE NUMERO_ID_SERVIDOR = %s",
            (str(ctx.guild.id),),
        )
        if resultado:
            sql = (
                "UPDATE SERVIDORES SET alert_channel = %s"
                " WHERE NUMERO_ID_SERVIDOR = %s"
            )
            ok = await self.pg.aupdate(sql, (channel.id, str(ctx.guild.id)))
        else:
            sql = (
                "INSERT INTO SERVIDORES (NOME_SERVIDOR, NUMERO_ID_SERVIDOR, alert_channel)"
                " VALUES (%s, %s, %s)"
            )
            ok = await self.pg.aupdate(
                sql, (ctx.guild.name, str(ctx.guild.id), channel.id)
            )
        if ok:
            await ctx.send(f"Canal de alertas definido para {channel.mention}.")
        else:
            await ctx.send("Ocorreu um erro ao definir o canal de alertas.")

    # ------------------------------------------------------------------ #
    # Aniversarios
    # ------------------------------------------------------------------ #
    async def _check_birthdays(self, today: date):
        """Envia parabens para quem faz aniversario hoje."""
        if not self.pg:
            return
        sql = (
            "SELECT u.USER_ID_DISCORD, s.NUMERO_ID_SERVIDOR, s.alert_channel"
            " FROM USUARIOS u, SERVIDORES s"
            " WHERE u.SERVIDOR_ID = s.ID_SERVIDORES"
            " AND u.birthday IS NOT NULL"
            " AND EXTRACT(MONTH FROM u.birthday) = %s"
            " AND EXTRACT(DAY FROM u.birthday) = %s"
        )
        resultado = await self.pg.aquery(sql, (today.month, today.day)) or []

        por_servidor = {}
        for row in resultado:
            por_servidor.setdefault(row["numero_id_servidor"], []).append(row)

        for guild_id, rows in por_servidor.items():
            mencoes = " ".join("<@" + str(row["user_id_discord"]) + ">" for row in rows)
            await self._send_alert(
                guild_id,
                rows[0]["alert_channel"],
                f"Hoje e aniversario de {mencoes}. Parabens!",
            )
            log.info("Aniversarios notificados no servidor %s: %s", guild_id, len(rows))

    @tasks.loop(minutes=BIRTHDAY_INTERVAL_MIN)
    async def birthday_loop(self):
        """Verifica uma vez por dia se alguem faz aniversario."""
        today = datetime.now(TZ_BRASIL).date()
        if today == self._last_birthday_date:
            return
        self._last_birthday_date = today
        try:
            await self._check_birthdays(today)
        except Exception as error:  # pylint: disable=broad-exception-caught
            log.error("Erro ao verificar aniversarios: %s", error, exc_info=1)

    @birthday_loop.before_loop
    async def before_birthday_loop(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Twitch
    # ------------------------------------------------------------------ #
    async def _get_twitch_token(self):
        """Obtem/renova o token de app da Twitch."""
        agora = time.time()
        if self._twitch_token and agora < self._twitch_token_expires - 60:
            return self._twitch_token
        body = {
            "client_id": os.environ["TWITCH_CLIENT_ID"],
            "client_secret": os.environ["TWITCH_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        }
        async with self._get_session().post(
            TWITCH_TOKEN_URL, data=body, timeout=15
        ) as resp:
            if resp.status != 200:
                log.warning("Falha ao obter token da Twitch: %s", resp.status)
                return self._twitch_token
            payload = await resp.json()
        self._twitch_token = payload.get("access_token")
        self._twitch_token_expires = agora + int(payload.get("expires_in", 0))
        return self._twitch_token

    async def _fetch_twitch_live(self, usernames, retry=True):
        """Devolve um dict username -> dados da stream, apenas para quem esta live."""
        if not usernames:
            return {}
        token = await self._get_twitch_token()
        if not token:
            return {}
        headers = {
            "Client-ID": os.environ["TWITCH_CLIENT_ID"],
            "Authorization": "Bearer " + token,
        }
        params = [("user_login", username) for username in usernames]
        async with self._get_session().get(
            TWITCH_STREAMS_URL, params=params, headers=headers, timeout=20
        ) as resp:
            if resp.status == 401 and retry:
                self._twitch_token = None
                return await self._fetch_twitch_live(usernames, retry=False)
            if resp.status != 200:
                log.warning("Falha ao consultar streams da Twitch: %s", resp.status)
                return {}
            payload = await resp.json()
        live = {}
        for stream in payload.get("data", []):
            live[stream.get("user_login", "").lower()] = stream
        return live

    async def _check_twitch(self):
        """Verifica quem comecou a transmitir na Twitch."""
        if not self.pg:
            return
        if not os.getenv("TWITCH_CLIENT_ID") or not os.getenv("TWITCH_CLIENT_SECRET"):
            log.warning("Credenciais da Twitch ausentes, pulando checagem")
            return
        sql = (
            "SELECT u.USER_ID_DISCORD, u.twitch, s.NUMERO_ID_SERVIDOR, s.alert_channel"
            " FROM USUARIOS u, SERVIDORES s"
            " WHERE u.SERVIDOR_ID = s.ID_SERVIDORES"
            " AND u.twitch IS NOT NULL AND u.twitch <> ''"
        )
        resultado = await self.pg.aquery(sql) or []

        por_usuario = {}
        for row in resultado:
            username = twitch_username(row["twitch"])
            if username:
                por_usuario.setdefault(username, []).append(row)

        live = await self._fetch_twitch_live(list(por_usuario))

        for username, rows in por_usuario.items():
            esta_live = username in live
            estava_live = self._twitch_status.get(username, False)
            self._twitch_status[username] = esta_live
            if esta_live and not estava_live and self._twitch_initialized:
                stream = live[username]
                titulo = stream.get("title") or ""
                jogo = stream.get("game_name") or ""
                detalhe = " - ".join(part for part in [titulo, jogo] if part)
                for row in rows:
                    texto = (
                        "<@" + str(row["user_id_discord"]) + "> esta ao vivo na Twitch!"
                    )
                    if detalhe:
                        texto += " " + detalhe
                    texto += "\n" + row["twitch"]
                    await self._send_alert(
                        row["numero_id_servidor"], row["alert_channel"], texto
                    )
                log.info("Alerta de live da Twitch enviado: %s", username)
        self._twitch_initialized = True

    @tasks.loop(minutes=TWITCH_INTERVAL_MIN)
    async def twitch_loop(self):
        """Verifica transmissões na Twitch."""
        try:
            await self._check_twitch()
        except Exception as error:  # pylint: disable=broad-exception-caught
            log.error("Erro ao verificar Twitch: %s", error, exc_info=1)

    @twitch_loop.before_loop
    async def before_twitch_loop(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # YouTube
    # ------------------------------------------------------------------ #
    async def _youtube_get(self, url, params):
        """Faz um GET na API do YouTube."""
        params["key"] = os.environ["YOUTUBE_API_KEY"]
        async with self._get_session().get(
            url, params=params, timeout=20
        ) as resp:
            if resp.status != 200:
                log.warning("YouTube API status %s em %s", resp.status, url)
                return None
            return await resp.json()

    async def _resolve_youtube_channel(self, ref):
        """Resolve a referencia do canal para um channel id."""
        tipo, valor = ref
        if tipo == "channel":
            return valor
        params = {"part": "id"}
        if tipo == "user":
            params["forUsername"] = valor
        elif tipo == "handle":
            params["forHandle"] = valor
        else:
            return None
        payload = await self._youtube_get(YOUTUBE_CHANNELS_URL, params)
        if not payload:
            return None
        items = payload.get("items") or []
        return items[0]["id"] if items else None

    async def _fetch_latest_youtube_video(self, channel_id):
        """Devolve o video mais recente do canal (uploads), ou None."""
        payload = await self._youtube_get(
            YOUTUBE_CHANNELS_URL, {"part": "contentDetails", "id": channel_id}
        )
        if not payload:
            return None
        items = payload.get("items") or []
        if not items:
            return None
        playlist = (
            items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        if not playlist:
            return None
        payload = await self._youtube_get(
            YOUTUBE_PLAYLIST_ITEMS_URL,
            {"part": "snippet", "playlistId": playlist, "maxResults": 1},
        )
        if not payload:
            return None
        items = payload.get("items") or []
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        video_id = snippet.get("resourceId", {}).get("videoId")
        if not video_id:
            return None
        return {"videoId": video_id, "title": snippet.get("title") or ""}

    async def _check_youtube(self):
        """Verifica se algum canal postou um video novo."""
        if not self.pg:
            return
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key or api_key == YOUTUBE_PLACEHOLDER_KEY:
            log.warning("YOUTUBE_API_KEY ausente, pulando checagem")
            return
        sql = (
            "SELECT u.USER_ID_DISCORD, u.youtube, s.NUMERO_ID_SERVIDOR, s.alert_channel"
            " FROM USUARIOS u, SERVIDORES s"
            " WHERE u.SERVIDOR_ID = s.ID_SERVIDORES"
            " AND u.youtube IS NOT NULL AND u.youtube <> ''"
        )
        resultado = await self.pg.aquery(sql) or []

        canais = {}
        videos = {}
        alertas = {}
        for row in resultado:
            ref = youtube_channel_ref(row["youtube"])
            if not ref:
                continue
            if ref not in canais:
                canais[ref] = await self._resolve_youtube_channel(ref)
            channel_id = canais[ref]
            if not channel_id:
                continue
            if channel_id not in videos:
                videos[channel_id] = await self._fetch_latest_youtube_video(channel_id)
            video = videos[channel_id]
            if not video:
                continue
            anterior = self._youtube_latest.get(channel_id)
            self._youtube_latest[channel_id] = video["videoId"]
            if (
                anterior is not None
                and anterior != video["videoId"]
                and channel_id not in alertas
            ):
                alertas[channel_id] = (row, video)

        for channel_id, (row, video) in alertas.items():
            texto = (
                "<@" + str(row["user_id_discord"]) + "> postou um video novo no YouTube!"
            )
            if video["title"]:
                texto += " " + video["title"]
            texto += "\nhttps://www.youtube.com/watch?v=" + video["videoId"]
            await self._send_alert(
                row["numero_id_servidor"], row["alert_channel"], texto
            )
            log.info("Alerta de video do YouTube enviado: %s", channel_id)

    @tasks.loop(minutes=YOUTUBE_INTERVAL_MIN)
    async def youtube_loop(self):
        """Verifica videos novos no YouTube."""
        try:
            await self._check_youtube()
        except Exception as error:  # pylint: disable=broad-exception-caught
            log.error("Erro ao verificar YouTube: %s", error, exc_info=1)

    @youtube_loop.before_loop
    async def before_youtube_loop(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    @commands.Cog.listener()
    async def on_ready(self):
        """Inicia os loops apenas quando o bot esta conectado."""
        if self._loops_started:
            return
        self._loops_started = True
        self.birthday_loop.start()
        self.twitch_loop.start()
        self.youtube_loop.start()
        log.info("Loops de alertas iniciados")


async def setup(bot: commands.Bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Alerts(bot))
