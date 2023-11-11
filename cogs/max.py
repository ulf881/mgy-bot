"""
    Modulo com comandos para zuar o max
"""
import io
import logging
import aiohttp
import discord
from discord.ext import commands

log = logging.getLogger("max")


class Max(commands.Cog, name="MaxGay"):
    """
    Classe com comandos para zuar o max
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(aliases=["text", "texto"])
    async def txt(self, ctx: commands.Context):
        """Max Gay Yeah"""
        await ctx.channel.send("Max Gay Yeah!")

    @commands.command(aliases=["image", "imagem", "img", "fota"])
    async def frota(self, ctx: commands.Context):
        """Mostra imagem do frota"""
        async with aiohttp.ClientSession() as session:
            async with session.get("https://i.imgur.com/dvWqqcz.png") as resp:
                if resp.status != 200:
                    log.error("Erro ao enviar a mensagem do frota")
                    return await ctx.channel.send(
                        "Deu ruim ao carregar a imagem, mas o max é gay e gosta do leite do frota"
                    )
                data = io.BytesIO(await resp.read())
        # Deleta o comando
        await ctx.message.delete()
        await ctx.channel.send(file=discord.File(data, "cool_image.png"))

    @commands.command(aliases=["image2", "imagem2", "img2", "drowns", "down"])
    async def drown(self, ctx: commands.Context):
        """Mostra imagem do max drowns in cum"""
        async with aiohttp.ClientSession() as session:
            async with session.get("https://i.imgur.com/dsUPTgY.png") as resp:
                if resp.status != 200:
                    log.error("Erro ao enviar a mensagem do drowns in cum")
                    return await ctx.channel.send(
                        "Deu ruim ao carregar a imagem, mas o max é gay e gosta do leite do frota"
                    )
                data = io.BytesIO(await resp.read())
        # Deleta o comando
        await ctx.message.delete()
        await ctx.channel.send(file=discord.File(data, "cool_image.png"))


# The setup fucntion below is neccesarry. Remember we give bot.add_cog() the name of the class in this case SimpleCog.
# When we load the cog, we use the name of the file.
async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Max(bot))
