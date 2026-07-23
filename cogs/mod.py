"""
Modulo para games. AKA CrappyDungeon
"""

import logging
import os
from pathlib import Path
from random import randint
import re
import sys
import subprocess

import aiohttp
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
                "python3",
                "-m",
                "pip",
                "install",
                "-U",
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

    @commands.command(hidden=True)
    @commands.has_role("Staff")
    async def cookies(self, ctx: commands.Context):
        """Atualiza os cookies para uso dos comandos de música. Abra e faça login em uma aba anônima ou uma conta que não utiliza para durar mais tempo"""
        # project root
        ROOT = Path(__file__).resolve().parent.parent
        COOKIES_FILE = ROOT / "cookies.txt"
        try:
            if not ctx.message.attachments:
                return await ctx.send(
                    "Inclua o arquivo com os cookies.", delete_after=5
                )

            attachment = ctx.message.attachments[0]

            if COOKIES_FILE.exists():
                COOKIES_FILE.unlink()

            # Save it as cookies.txt regardless of the uploaded filename
            await attachment.save(COOKIES_FILE)

            await ctx.message.delete()
            await ctx.send("✅ cookies.txt atualizados")
            await self.restart(ctx)

        except Exception as e:
            await ctx.send(f"❌ Erro ao atualizar cookies:\n`{e}`")

    @commands.command(aliases=["dice", "dado", "rand", "rolar"])
    async def roll(self, ctx: commands.Context, dice: str):
        """Roda um dado no formato [quantidade]d[faces]
        exemplo: mgy roll 2d6
        exemplo2: mgy roll d20
        """
        # Regex to match the pattern, defaulting to 1 if no number is found before 'D'
        match = re.match(r"(\d*)d(\d+)", dice, re.IGNORECASE)

        if match:
            first_number = int(match.group(1)) if match.group(1) else 1
            second_number = int(match.group(2))
        else:
            return await ctx.send(
                "Dado invalido. Utilize mgy roll [quantidade]d[faces]"
            )

        for i in range(first_number):
            await ctx.send(print(randint(1, second_number)))

    @commands.command(hidden=True)
    async def instagram(self, ctx: commands.Context, url: str):
        """
        Gera um embedding para links do Instagram que não funcionam nativamente no Discord.
        O bot tentará várias alternativas de domínio até encontrar uma que funcione.

        Args:
            url (str): O link original do Instagram (ex: https://www.instagram.com/p/XXXXXXXXXXX/).
        """
        # Deferir a resposta para que o usuário saiba que o bot está processando o comando,
        # especialmente útil para operações que podem levar alguns segundos.
        await ctx.defer()

        alternative_domains = [
            "ddinstagram.com",
            "v.ddinstagram.com",  # Uma variante comum para ddinstagram
            "vxinstagram.com",
            "kgram.to",
            "instafix.net",
            # Adicione mais alternativas aqui à medida que se tornarem disponíveis
            # ou se as atuais pararem de funcionar.
        ]
        # Expressão regular para verificar se o URL contém um domínio do Instagram.
        # É flexível o suficiente para identificar posts, reels, etc., para substituição de domínio.
        instagram_domain_pattern = re.compile(r"(instagram\.com|instagr\.am)")

        # 1. Validar o URL de entrada para garantir que ele contenha um domínio do Instagram.
        original_domain_match = instagram_domain_pattern.search(url)
        if not original_domain_match:
            await ctx.reply(
                "Por favor, forneça um link válido do Instagram (deve conter `instagram.com` ou `instagr.am`)."
            )
            return

        original_domain = original_domain_match.group(0)

        found_working_embed = False
        # Itera sobre os domínios alternativos definidos.
        for alt_domain in alternative_domains:
            # Constrói o URL transformado, substituindo o domínio original do Instagram.
            transformed_url = url.replace(original_domain, alt_domain)

            try:
                # Usa aiohttp para fazer uma requisição HEAD. Isso é eficiente, pois
                # só busca os cabeçalhos (headers), não o conteúdo completo, para
                # verificar a acessibilidade do link.
                # `allow_redirects=True` garante que sigamos quaisquer redirecionamentos
                # que o serviço alternativo possa usar.
                # `timeout` evita que o bot fique aguardando indefinidamente.
                async with aiohttp.ClientSession() as session:
                    async with session.head(
                        transformed_url, allow_redirects=True, timeout=10
                    ) as response:
                        # Se o status da resposta for 200 OK, consideramos este um link
                        # potencialmente incorporável, pois o serviço alternativo está acessível.
                        if response.status == 200:
                            # Envia apenas o link transformado para que o Discord tente incorporá-lo.
                            await ctx.send(transformed_url)
                            found_working_embed = True
                            break  # Para após a primeira tentativa bem-sucedida
                        # Não há necessidade de enviar uma mensagem se uma alternativa falhou com um status diferente de 200,
                        # pois o usuário não quer ver o processo.
            except aiohttp.ClientError:
                # Captura erros específicos do cliente aiohttp (por exemplo, problemas de DNS, conexão recusada).
                # Não envia mensagem ao usuário sobre a falha.
                pass
            except Exception:
                # Captura quaisquer outros erros inesperados durante o processo.
                # Não envia mensagem ao usuário sobre a falha.
                pass

        # Se nenhum link incorporável foi encontrado após tentar todas as alternativas.
        if not found_working_embed:
            await ctx.send(
                "Não foi possível encontrar uma alternativa de embed funcional para o seu link do Instagram. "
                "As alternativas podem mudar com o tempo ou o link pode ser privado/inexistente."
            )

    @commands.command(hidden=True)
    async def twitter(self, ctx: commands.Context, url: str):
        """
        Gera um embedding para links do Twitter/X que não funcionam nativamente no Discord.
        O bot tentará usar fxtwitter.com como serviço alternativo.

        Args:
            url (str): O link original do Twitter/X (ex: https://twitter.com/user/status/XXXXXXXXXXX ou https://x.com/user/status/XXXXXXXXXXX).
        """
        # Deferir a resposta para que o usuário saiba que o bot está processando o comando.
        await ctx.defer()

        # Domínio alternativo principal para Twitter/X.
        # fxtwitter.com é um serviço popular para melhorar embeds de tweets no Discord.
        alternative_domain = "fxtwitter.com"

        # Expressão regular para verificar se o URL contém um domínio do Twitter/X.
        # Captura tanto 'twitter.com' quanto 'x.com'.
        twitter_domain_pattern = re.compile(r"(twitter\.com|x\.com)")

        # 1. Validar o URL de entrada para garantir que ele contenha um domínio do Twitter/X.
        original_domain_match = twitter_domain_pattern.search(url)
        if not original_domain_match:
            await ctx.reply(
                "Por favor, forneça um link válido do Twitter/X (deve conter `twitter.com` ou `x.com`)."
            )
            return

        original_domain = original_domain_match.group(0)

        # Constrói o URL transformado, substituindo o domínio original.
        # Garante que o protocolo (http/https) seja mantido.
        # Se o link original já tiver um subdomínio como 'pbs.twimg.com' para mídias,
        # isso não será tratado, focando apenas nos links de status/postagens.
        transformed_url = url.replace(original_domain, alternative_domain)

        try:
            # Usa aiohttp para fazer uma requisição HEAD.
            # `allow_redirects=True` para seguir redirecionamentos.
            # `timeout` para evitar esperas longas.
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    transformed_url, allow_redirects=True, timeout=10
                ) as response:
                    # Se o status da resposta for 200 OK, considera que o embed pode funcionar.
                    if response.status == 200:
                        # Envia apenas o link transformado para que o Discord tente incorporá-lo.
                        await ctx.send(transformed_url)
                    else:
                        # Se fxtwitter.com não retornar 200 OK, informa o usuário.
                        await ctx.send(
                            f"Não foi possível gerar um embed usando `{alternative_domain}` para o link fornecido. "
                            f"Status HTTP: `{response.status}`. "
                            "O link pode ser privado, inexistente ou o serviço fxtwitter.com pode estar com problemas."
                        )
        except aiohttp.ClientError:
            # Captura erros de conexão (DNS, conexão recusada, etc.).
            await ctx.send(
                "Ocorreu um erro de conexão ao tentar gerar o embed para o seu link do Twitter/X. "
                "Verifique o link ou tente novamente mais tarde."
            )
        except Exception as e:
            # Captura quaisquer outros erros inesperados.
            await ctx.send(
                f"Ocorreu um erro inesperado: `{e}` ao tentar gerar o embed para o seu link do Twitter/X."
            )


async def setup(bot: commands.Bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Mod(bot))
