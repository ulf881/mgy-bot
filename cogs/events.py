"""
    Modulo cuidar dos eventos on_SOMETHING
"""

import io
import logging
from random import randint
from datetime import datetime, timedelta
import aiohttp
import discord

from discord.ext import commands
from cogs.level import Level
from utils.pgdatabase import Postgres

log = logging.getLogger("Eventos")

DELAY = 45


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
        self.level = Level(bot)
        self.lista_delay = [{}]
        self.acoes = []  # acoes para game
        self.kick_list = [229043445010923520]  # TODO - add to kicklist

    async def delay(self, author: int):
        """Implementa delay entre ganhos de xp"""
        # Assume que nao passou o tempo
        result = 0
        now = datetime.now()
        try:
            indice = [
                (i) for i, d in enumerate(self.lista_delay) if author in d.values()
            ]
            if not indice:
                result = 1  # Pode ganhar xp
                self.lista_delay.append({"id": author, "hora": now})
            else:
                dif: timedelta = now - self.lista_delay[indice[0]].get("hora")

                # Verifica se passou mais de DELAY segundos
                if dif.seconds > DELAY:
                    result = 1  # Pode ganhar exp
                    self.lista_delay.pop(indice[0])
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error("Erro ao verificar delay: %s", e, exc_info=1)

        return result

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Metodo que trata cada mensagem enviada"""
        log.info(
            "%s: %s: %s: %s",
            message.channel,
            message.author,
            message.author.name,
            message.content,
        )

        # Pega canal default
        if message.guild.id == 1192899104330743998:
            default_channel = self.bot.get_channel(
                1192899105781993535
            )  # Staff random shit
        else:
            default_channel = self.bot.get_channel(message.channel.id)

        # Verifica BOT, DELAY e executa atualizacao de xp, exibe msg level up se necessaria
        if not message.author.bot:
            if await self.delay(message.author.id):
                evoluiu = await self.level.update(message)
                if evoluiu:
                    await default_channel.send(
                        "Finalmente "
                        + message.author.mention
                        + " upou para o nível "
                        + str(evoluiu)
                        + "! Glória a Deuxxx"
                    )
            else:  # atualiza apenas total de mensagens
                await self.level.update_total_messages(message)

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
                log.info("counterLembra: %s", str(self.counter_lembra))

            if self.counter_frota >= 20 and randint(1, 100) <= 24:
                self.counter_frota = 0

                async with aiohttp.ClientSession() as session:
                    async with session.get("https://i.imgur.com/dvWqqcz.png") as resp:
                        if resp.status != 200:
                            return await print("Deu ruim ao carregar imagem")
                        data = io.BytesIO(await resp.read())
                await default_channel.send(file=discord.File(data, "cool_image.png"))

            else:
                log.info("counterFrota: %s", self.counter_frota)

        # 1% de chance de kickar o usuario doc canal de voz e excluir sua msg
        if message.author.id in self.kick_list:
            if randint(1, 200) <= 1:
                try:
                    log.info("Kickando user")
                    pending_command = self.bot.get_command("move")
                    ctx = await self.bot.get_context(message)
                    await ctx.invoke(pending_command, message.author.id, "vaza")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error("Erro ao kickar user %s", e, exc_info=1)

        if message.content == "mgy":
            await message.channel.purge(limit=1)
            await message.channel.send("Max Gay Yeah!")

        if message.content == "lenny":
            # await message.delete()
            await message.channel.purge(limit=1)
            await message.channel.send("( ͡° ͜ʖ ͡°)")

        # TODO - automatizar mensangem no ano novo. Também automatizar mensagens customizadas em dias de aniversario, etc...
        if message.content == "novo":
            await message.channel.purge(limit=1)
            await message.channel.send(
                "Só estou passando aqui pra desejar um feliz ano novo! E lembrar o que o Max Gay. Bittenca Viadin. Jonas Líder. 24 Deus. Isaac Best Game."
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
                else:
                    pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """Método que trata erros"""
        # log.error(ctx.command.__dict__)
        if isinstance(error, commands.CommandNotFound):
            log.error("Comando inexistente")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        else:
            log.error("Erro ao executar comando, %s", error, exc_info=1)


async def setup(bot: commands.Bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Eventos(bot))
