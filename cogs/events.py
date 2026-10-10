"""
Modulo cuidar dos eventos on_SOMETHING
"""

import io
import logging
import os
from datetime import datetime, timedelta
from random import randint

import aiohttp
import discord
from discord.ext import commands

from utils.config import FROTA_IMAGE_URL
from utils.pgdatabase import Postgres

log = logging.getLogger("Eventos")

DELAY = 45
MACRO_GUILD_ID = 1192899104330743998
STAFF_CHANNEL_ID = 1192899105781993535


class Eventos(commands.Cog, name="Eventos"):
    """
    Classe para cuidar dos eventos on_SOMETHING
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pg = Postgres()
        self.counter_lembra = 0
        self.counter_frota = 0
        self.voice_id = 0
        self._level = None
        self.xp_delay: dict[int, datetime] = {}
        self.acoes = []  # acoes para game
        self.kick_list = [229043445010923520]  # TODO - add to kicklist
        self._session: aiohttp.ClientSession | None = None

    async def cog_unload(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        """Retorna uma ClientSession compartilhada do cog."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_level(self):
        """Reutiliza o cog Level carregado; cria um fallback se necessario."""
        level = self.bot.get_cog("Level")
        if level is None:
            if self._level is None:
                from cogs.level import Level

                self._level = Level(self.bot)
            return self._level
        return level

    def delay(self, author: int) -> int:
        """Implementa delay entre ganhos de xp."""
        now = datetime.now()
        last = self.xp_delay.get(author)
        if last is not None and (now - last).total_seconds() <= DELAY:
            return 0

        self.xp_delay[author] = now
        # Evita crescimento ilimitado do dicionario.
        if len(self.xp_delay) > 1000:
            cutoff = now - timedelta(seconds=DELAY * 10)
            self.xp_delay = {
                uid: ts for uid, ts in self.xp_delay.items() if ts >= cutoff
            }
        return 1

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Metodo que trata cada mensagem enviada"""
        # Ignora mensagens diretas (sem guild) para nao quebrar em message.guild.id
        if message.guild is None:
            return

        log.debug(
            "%s: %s: %s",
            message.channel,
            message.author,
            message.content,
        )

        # Pega canal default
        if message.guild.id == MACRO_GUILD_ID:
            default_channel = self.bot.get_channel(STAFF_CHANNEL_ID)  # Staff random shit
        else:
            default_channel = self.bot.get_channel(message.channel.id)

        # Verifica BOT, DELAY e executa atualizacao de xp, exibe msg level up se necessaria
        if not message.author.bot:
            level = self._get_level()
            if self.delay(message.author.id):
                evoluiu = await level.update(message)
                if evoluiu:
                    await default_channel.send(
                        "Finalmente "
                        + message.author.mention
                        + " upou para o nível "
                        + str(evoluiu)
                        + "! Glória a Deuxxx"
                    )
            else:  # atualiza apenas total de mensagens
                await level.update_total_messages(message)

        # Detectada mensagem do Max
        if message.author.id == 229043445010923520:
            await message.add_reaction("<:okgay:1193368846321586250>")
            self.counter_lembra += 1
            self.counter_frota += 1

            if self.counter_lembra >= 14 and randint(1, 100) <= 24:
                await default_channel.send(
                    "Só estou passando aqui para lembrar a todos que o Max é gay."
                )
                self.counter_lembra = 0
            else:
                log.debug("counterLembra: %s", str(self.counter_lembra))

            if self.counter_frota >= 20 and randint(1, 100) <= 24:
                self.counter_frota = 0

                session = self._get_session()
                async with session.get(FROTA_IMAGE_URL) as resp:
                    if resp.status != 200:
                        log.error("Deu ruim ao carregar imagem: %s", resp.status)
                        return
                    data = io.BytesIO(await resp.read())
                await default_channel.send(file=discord.File(data, "cool_image.png"))

            else:
                log.debug("counterFrota: %s", str(self.counter_frota))

        # 1% de chance de kickar o usuario do canal de voz
        if message.author.id in self.kick_list:
            if randint(1, 200) <= 1:
                try:
                    log.info("Kickando user")
                    pending_command = self.bot.get_command("move")
                    if pending_command is not None:
                        ctx = await self.bot.get_context(message)
                        await ctx.invoke(pending_command, message.author.id, "vaza")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error("Erro ao kickar user %s", e, exc_info=1)

        if message.content == "mgy":
            await message.channel.purge(limit=1)
            await message.channel.send(os.environ["MACRO"])

        if message.content == "lenny":
            await message.channel.purge(limit=1)
            await message.channel.send("( ͡° ͜ʖ ͡°)")

        # TODO - automatizar mensagem no ano novo.
        if message.content == "novo":
            await message.channel.purge(limit=1)
            await message.channel.send(
                "Só estou passando aqui pra desejar um feliz ano novo! E lembrar o que "
                + os.environ["MACRO"]
            )

        # Verifica se esta in game
        if self.bot.game:
            self.bot.total_mensagem += 1
            if not message.author.bot:
                try:
                    action = int(message.content)
                    self.bot.acoes.append(action)
                except ValueError:
                    pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """Método que trata erros"""
        if isinstance(error, commands.CommandNotFound):
            log.error("Comando inexistente")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        else:
            original = getattr(error, "original", error)
            log.error(
                "Erro ao executar comando, %s",
                error,
                exc_info=(type(original), original, original.__traceback__),
            )


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Eventos(bot))
