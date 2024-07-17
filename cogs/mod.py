"""
    Modulo para games. AKA CrappyDungeon
"""

import logging
import os
import sys
import subprocess

import discord
from discord import ChannelType
from discord.ext import commands

from utils.pgdatabase import Postgres

log = logging.getLogger("Mod")


def switch(guild_id: int):
    """Switch case para pegar macro"""
    print(guild_id)
    return {
        1192899104330743998: os.environ["MACRO"],
        582709300506656792: os.environ["MACRO2"],
    }.get(guild_id, "MGY")


class Mod(commands.Cog, name="Mod"):
    """
    Moderation tools, staff only
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pg = Postgres()

    @commands.command(aliases=["del", "rem"])
    @commands.has_role("Staff")
    async def purge(self, ctx: commands.Context, quantidade: int):
        """Deleta as ultimas `n` mensagens do servidor. Staff only

        Limite 50 pra evitar bosta."""
        if int(quantidade) > 50:
            quantidade = 50
        # TODO SAVE MESSAGES TO ROLLBACK
        await ctx.channel.purge(limit=int(quantidade) + 1)

    @commands.command(hidden=True)
    @commands.has_role("Staff")
    async def mute(self, ctx: commands.Context, user_id: int):
        """Deixa usuario mudo"""
        await ctx.message.delete()
        user_obj = await ctx.guild.fetch_member(user_id)
        await user_obj.edit(mute=True)

    @commands.command(hidden=True)
    @commands.has_role("Staff")
    async def restart(self, ctx: commands.Context):
        """Reset all"""
        await ctx.send("```Updating & restarting, aguarde uns 10-20s...```")
        subprocess.check_call(
            [
                "sudo",
                "python3",
                "-m",
                "pip",
                "install",
                "--U",
                "--pre",
                "yt-dlp[default]",
            ]
        )
        os.execl(sys.executable, sys.executable, *sys.argv)

    @commands.command(hidden=True)
    @commands.has_role("Staff")
    async def audio(self, ctx: commands.Context, user_id: int):
        """Deixa usuario sem audio"""
        await ctx.message.delete()
        user_obj = await ctx.guild.fetch_member(user_id)
        await user_obj.edit(deafen=True)

    @commands.command(hidden=True)
    @commands.has_role("Staff")
    async def move(self, ctx: commands.Context, user_id: int, voice: str):
        """Move usuario para outro canal de voz"""

        channel = discord.utils.find(
            lambda c: c.name == voice and c.type == ChannelType.voice,
            ctx.message.guild.channels,
        )

        await ctx.message.delete()
        print(await ctx.guild.fetch_member(user_id))
        user_obj = await ctx.guild.fetch_member(user_id)
        await user_obj.move_to(channel)

    @commands.command(aliases=["server", "reg", "regiao"])
    @commands.has_role("Staff")
    async def region(self, ctx: commands.Context, *args):
        """Altera ou reseta a região do servidor. Staff only

        Args:
        Sem argumentos reseta Brasil
        us para us-south
        nome completo para outros.
        """
        try:
            if "us" in args:
                new_reg = "us-south"
            elif not args:
                new_reg = "us-south"
                await ctx.author.voice.channel.edit(rtc_region=new_reg)
                new_reg = "brazil"

            await ctx.author.voice.channel.edit(rtc_region=new_reg)
            await ctx.send("Alterado para região: " + new_reg)
            log.info("Alterado para região: %d", new_reg)
        except Exception as error:  # pylint: disable=broad-except
            await ctx.send(
                "```Erro ao alterar para a regiao: "
                + new_reg
                + ". Verifique as permissões e que está conectado em um canal de voz```"
            )
            log.error(error)

    @commands.command(aliases=["inf"])
    async def info(self, ctx: commands.Context):
        """Mostra info sobre o membro mencionado.

        Se não mencionar um membro suas informações são exibidas.
        Exemplo: mgy info @MGY"""
        count = 0
        total = 0
        links = ""
        if ctx.message.mentions:
            mention = ctx.message.mentions[0]
        else:
            mention = ctx.author

        sql = "select * from USUARIOS,NIVEIS,SERVIDORES"
        sql += " WHERE USER_ID_DISCORD = '" + str(mention.id) + "'"
        sql += " AND NUMERO_ID_SERVIDOR = '" + str(ctx.guild.id) + "'"
        sql += " and NIVEL_ID = NIVEIS.ID_NIVEIS"
        sql += " and SERVIDOR_ID = SERVIDORES.ID_SERVIDORES"

        resultado = self.pg.query(sql)
        if resultado[0]["youtube"]:
            links = "[youtube]" + "(" + resultado[0]["youtube"] + ")"
        if resultado[0]["twitch"]:
            links += ", [twitch]" + "(" + resultado[0]["twitch"] + ")"
        if resultado[0]["twitter"]:
            links += ", [twitter]" + "(" + resultado[0]["twitter"] + ")"
        if resultado[0]["outros"]:
            outros = resultado[0]["outros"].split(",")
            for name_link in outros:
                # separa o nome do link
                field = name_link.split(" ")
                log.info(field)
                links += ", [" + field[0] + "]" + "(" + field[1] + ")"

        embed = discord.Embed(colour=mention.color)

        # Ajustar url do avatar (Tratativa pra caso user não possua avatar)
        mention_url = ""
        if mention.avatar and mention.avatar.url:
            mention_url = mention.avatar.url

        embed.set_author(
            name=mention.name,
            url=mention_url,
            icon_url=mention_url,
        )

        embed.add_field(name="Mensagens eviadas", value="Calculando...")
        embed.add_field(
            name="Nível atual",
            value=str(resultado[0]["nivel_id"]) + "-" + resultado[0]["nome_nivel"],
        )
        embed.add_field(name="Expêriencia", value=resultado[0]["experiencia"])
        if len(links) > 0:
            embed.add_field(name="Links", value=links)
        # goto
        if mention.id == 231585079682400256:
            embed.add_field(name="Perdido", value="Sim")
        # daniel
        if mention.id == 369219244560351233:
            embed.add_field(name="Vacilão", value="Sim")
        # max
        if mention.id == 229043445010923520:
            embed.add_field(name="Gay", value="Sim")
        # bittenca
        if mention.id == 1192914110459936829:
            embed.add_field(name="Viadin", value="Sim")
        # lider
        if mention.id == 159598240726122496:
            embed.add_field(name="Lider", value="Sim")

        embed.set_footer(
            text="Veja como customizar seus Links do Info com mgy help update",
            icon_url="https://cdn.discordapp.com/avatars/596088044877119507/0d26138b572e7dfffc6cab54073cdb31.webp",
        )  # pylint: disable=line-too-long

        message = await ctx.send(embed=embed)

        for channel in ctx.guild.text_channels:
            async for msg in channel.history(limit=None):
                if msg.author == mention:
                    count += 1
                total += 1
        # TODO - Separar no canal  atual, e total de todos
        embed.set_field_at(index=0, name="Mensagens enviadas", value=str(count))
        # TODO - Info do canal/server
        # embed.set_field_at(index=1, name="Total", value=str(total))
        if message:
            await message.edit(embed=embed)

    @commands.command(aliases=["up"])
    async def update(
        self,
        ctx: commands.Context,
        column: str = commands.parameter(
            description="youtube | twitch | twitter | instagram | outros"
        ),
        arg1: str = commands.parameter(
            description="Seu link. Ou caso esteja inserindo 'outros', o nome do site"
        ),
        arg2=commands.parameter(
            default=None, description="O link caso esteja inserindo em 'outros'"
        ),
    ):
        """Permite dar update nos seus links.

        Links são youtube/twitter/twitch/instagram/outros. Use: 'mgy info' para ver seus links.
        Exemplo: mgy update outros name link
        Exemplo2: mgy update youtube link

        Você pode inserir em 'outros' multiplas vezes (um link por chamada do comando)
        """
        args = arg1
        colunas = ["youtube", "twitch", "twitter", "instagram", "outros"]
        if column not in colunas:
            await ctx.send(column + " não existe. Tente inserir em 'outros'")

        sql = "select * from USUARIOS,NIVEIS,SERVIDORES"
        sql += " WHERE USER_ID_DISCORD = '" + str(ctx.author.id) + "'"
        sql += " AND NUMERO_ID_SERVIDOR = '" + str(ctx.guild.id) + "'"
        sql += " AND NIVEL_ID = NIVEIS.ID_NIVEIS"
        sql += " AND SERVIDOR_ID = SERVIDORES.ID_SERVIDORES"
        resultado = self.pg.query(sql)

        if column == "outros":
            if not arg2:
                await ctx.send("Para coluna outros é necessário passar o nome e o link")
                return
            args += " " + arg2

            if resultado[0]["outros"]:
                args += "," + (resultado[0]["outros"])

        sql = "UPDATE USUARIOS SET " + column + " = '" + args + "'"
        sql += " WHERE ID_USUARIOS = '" + str(resultado[0]["id_usuarios"]) + "'"

        if self.pg.update(sql):
            await ctx.send("Atualizado")
        else:
            await ctx.send("Ocorreu um erro ao atualizar")

    @commands.command(aliases=["git", "dev"])
    async def github(self, ctx: commands.Context):
        await ctx.send(
            "Colabore com o desenvolvimento do bot: https://github.com/ulf881/mgy-bot"
        )


async def setup(bot: commands.Bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Mod(bot))
