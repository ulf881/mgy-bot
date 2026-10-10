"""
Modulo com comandos para zuar o max
"""

import io
import logging

import aiohttp
import discord
from discord.ext import commands

from utils.config import DROWN_IMAGE_URL, FROTA_IMAGE_URL

log = logging.getLogger("max")

IMGUR_ERROR_MESSAGE = (
    "Deu ruim ao carregar a imagem, mas o max é gay e gosta do leite do frota"
)


class Max(commands.Cog, name="MaxGay"):
    """
    Classe com comandos para zuar o max
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_unload(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _send_image(self, ctx: commands.Context, url: str, log_label: str):
        """Baixa a imagem e envia no canal, deletando o comando do usuario."""
        async with self._get_session().get(url) as resp:
            if resp.status != 200:
                log.error("Erro ao enviar a mensagem do %s", log_label)
                return await ctx.channel.send(IMGUR_ERROR_MESSAGE)
            data = io.BytesIO(await resp.read())
        # Deleta o comando
        await ctx.message.delete()
        await ctx.channel.send(file=discord.File(data, "cool_image.png"))

    @commands.command(aliases=["text", "texto"])
    async def txt(self, ctx: commands.Context):
        """Max Gay Yeah"""
        await ctx.channel.send("Max Gay Yeah!")

    @commands.command(aliases=["image", "imagem", "img", "fota"])
    async def frota(self, ctx: commands.Context):
        """Mostra imagem do frota"""
        await self._send_image(ctx, FROTA_IMAGE_URL, "frota")

    @commands.command(aliases=["image2", "imagem2", "img2", "drowns", "down"])
    async def drown(self, ctx: commands.Context):
        """Mostra imagem do max drowns in cum"""
        await self._send_image(ctx, DROWN_IMAGE_URL, "drowns in cum")


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Max(bot))
