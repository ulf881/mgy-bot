"""
    Modulo cuidar dos niveis dos usuarios
"""
import os
import logging
import discord
from random import randint

from discord.ext import commands
from discord.utils import get

from utils.pgdatabase import Postgres

log = logging.getLogger("Level")
BASE = 10  # Toda mensagem ganha a xp base
MAX_RAND = 14  # Toda mensagem ganha aleatorio entre 1 e este valor
MAX_LEVEL = 51  # Nivel máximo
MULTIPLER = 1.1  # O quanto de XP a mais precisa em comparação ao lvl anterior


def switchGuild(guild_id: int):
    """Switch case para pegar macro"""
    print(guild_id)
    return {
        1192899104330743998: os.environ["MACRO"],
        582709300506656792: os.environ["MACRO2"],
    }.get(guild_id, "MGY")


def switch(x):
    """Switch case para pegar o novo cargo"""
    return {
        "0": "sem role",
        "1": "Rookies (lvl 1 - 5)",
        "2": "Rookies (lvl 1 - 5)",
        "3": "Rookies (lvl 1 - 5)",
        "4": "Rookies (lvl 1 - 5)",
        "5": "Rookies (Lvl 1 - 5)",
        "6": "Adventurers (lvl 6 - 10)",
        "7": "Adventurers (lvl 6 - 10)",
        "8": "Adventurers (lvl 6 - 10)",
        "9": "Adventurers (lvl 6 - 10)",
        "10": "Adventurers (lvl 6 - 10)",
        "11": "Veterans (lvl 11 - 15)",
        "12": "Veterans (lvl 11 - 15)",
        "13": "Veterans (lvl 11 - 15)",
        "14": "Veterans (lvl 11 - 15)",
        "15": "Veterans (lvl 11 - 15)",
        "16": "Monarchs (Lvl 16 - 20)",
        "17": "Monarchs (Lvl 16 - 20)",
        "18": "Monarchs (Lvl 16 - 20)",
        "19": "Monarchs (Lvl 16 - 20)",
        "20": "Monarchs (Lvl 16 - 20)",
        "21": "Kings (Lvl 21 - 25)",
        "22": "Kings (Lvl 21 - 25)",
        "23": "Kings (Lvl 21 - 25)",
        "24": "Kings (Lvl 21 - 25)",
        "25": "Kings (Lvl 21 - 25)",
        "26": "Emperors (Lvl 26 - 30)",
        "27": "Emperors (Lvl 26 - 30)",
        "28": "Emperors (Lvl 26 - 30)",
        "29": "Emperors (Lvl 26 - 30)",
        "30": "Emperors (Lvl 26 - 30)",
        "31": "The Living Legends (Lvl 31 - 35)",
        "32": "The Living Legends (Lvl 31 - 35)",
        "33": "The Living Legends (Lvl 31 - 35)",
        "34": "The Living Legends (Lvl 31 - 35)",
        "35": "The Living Legends (Lvl 31 - 35)",
        "36": "The Ascended Ones (Lvl 36 - 40)",
        "37": "The Ascended Ones (Lvl 36 - 40)",
        "38": "The Ascended Ones (Lvl 36 - 40)",
        "39": "The Ascended Ones (Lvl 36 - 40)",
        "40": "The Ascended Ones (Lvl 36 - 40)",
        "41": "Lesser Gods (Lvl 41 - 45)",
        "42": "Lesser Gods (Lvl 41 - 45)",
        "43": "Lesser Gods (Lvl 41 - 45)",
        "44": "Lesser Gods (Lvl 41 - 45)",
        "45": "Lesser Gods (Lvl 41 - 45)",
        "46": "Greater Gods (Lvl 46 - 50)",
        "47": "Greater Gods (Lvl 46 - 50)",
        "48": "Greater Gods (Lvl 46 - 50)",
        "49": "Greater Gods (Lvl 46 - 50)",
        "50": "Greater Gods (Lvl 46 - 50)",
        "51": "Assembly of the Seven (Lvl 51+)",
        "52": "God",
    }.get(x, "")


class Level(commands.Cog, name="Level"):
    """
    Classe para cuidar dos eventos de level
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pg = Postgres()

    async def update_role(
        self, user: discord.Member, role_atual: int, guild: discord.Guild
    ):
        """Atualiza cargo"""
        role = get(guild.roles, name="")
        new_role = switch(str(role_atual + 1))
        curr_role = switch(str(role_atual))
        if new_role:
            if curr_role:
                if new_role != curr_role:
                    log.info(
                        "atualizando cargo de: "
                        + str(role_atual)
                        + " para: "
                        + str(role_atual + 1)
                    )
                    try:
                        role = get(guild.roles, name=new_role)
                        if not role:
                            role = await guild.create_role(
                                name=new_role,
                                colour=discord.Colour(0x992D22),
                                hoist=True,
                            )
                            # role.hoist = True
                        await user.add_roles(role)
                    except Exception as e:
                        log.error("Erro ao atribuir cargo, " + str(e))
                        pass
                    try:
                        role = get(guild.roles, name=curr_role)
                        if role and (role_atual != 0):
                            await user.remove_roles(role)
                    except Exception as e:
                        log.error("Erro ao remover cargo, " + str(e))
                        pass

    async def prox_nivel(self, nivel_atual: int):
        """Verifica a quantidade de exp pro proximo nivel"""
        nextl = 0
        nivel = 1000
        total = 1000  # level 1
        for i in range(1, nivel_atual):
            nextl = nivel * MULTIPLER
            nextl = nextl - nivel
            nivel += nextl
            total += nivel
            # Para ver a tabela de levels:
            # lista.append(
            #     {
            #         "nivel": i,
            #         "xp": int(total - nivel - nivel + nextl),  # xp minima pro lvl
            #         "próx": int(nivel - nextl),  # total necessário pro próx nivel
            #         "a mais": int(nextl),  # mais que o anterior
            #         # "max": int(total - nivel),
            #     }
            # )

        return total

    async def find_user(self, author: int, guild: int):
        """Consulta usuario"""
        if not self.pg:
            return
        sql = "select * from USUARIOS,NIVEIS,SERVIDORES"
        sql += " WHERE USER_ID_DISCORD = '" + str(author) + "'"
        sql += " AND NUMERO_ID_SERVIDOR = '" + str(guild) + "'"
        sql += " and NIVEL_ID = NIVEIS.ID_NIVEIS"
        sql += " and SERVIDOR_ID = SERVIDORES.ID_SERVIDORES"

        resultado = self.pg.query(sql)
        return resultado

    async def update_user(self, info, user: discord.Member, guild: discord.Guild):
        """atualiza exp e evolui"""
        if not self.pg:
            return
        level_atual = int(info[0]["nivel_id"])
        result = 0
        experiencia = int(BASE + randint(0, MAX_RAND + int(level_atual * 0.5)))
        if self.bot.bonusXP:
            experiencia *= 2
        experiencia_atual = int(info[0]["experiencia"])

        # Prepara sql para atualizar exp
        sql = (
            "update usuarios set experiencia = '"
            + str(experiencia_atual + experiencia)
            + "'"
        )

        # Verifica se evoluiu
        experiencia_necessaria = await self.prox_nivel(level_atual)
        if (experiencia_atual + experiencia) >= int(experiencia_necessaria):
            # Verifica se nao esta no nivel maximo
            if level_atual < MAX_LEVEL:
                sql += ", nivel_id = " + str(level_atual + 1)  # Evolui
                result = level_atual + 1
                await self.update_role(user, info[0]["nivel_id"], guild)

        # Atualiza total de menagens
        sql += ", TOTAL_MENSAGENS = " + str(int(info[0]["total_mensagens"]) + 1)
        sql += " where id_usuarios = " + str(info[0]["id_usuarios"])

        self.pg.update(sql)
        return result

    async def insere_usuario(self, guild: discord.Guild, author: discord.Member):
        """Insere usuario"""
        if not self.pg:
            return
        log.info("Inserindo usuario")
        # busca id_servidor
        sql = "select * from SERVIDORES"
        sql += " WHERE NUMERO_ID_SERVIDOR = '" + str(guild.id) + "'"

        resultado = self.pg.query(sql)

        # Guild deve ser inserida antes no bd
        if not resultado:
            try:
                log.info("Inserindo usuario em " + str(guild.id))
                sql = "insert into SERVIDORES (NOME_SERVIDOR, NUMERO_ID_SERVIDOR)"
                sql += " values ('" + str(guild.name) + "', '" + str(guild.id) + "')"

                self.pg.update(sql)
                log.info("Guild " + guild.name + "adicionada")
            except Exception as e:
                log.error("Erro ao inserir guild " + str(e))
                raise
        else:
            sql = "insert into USUARIOS (NOME_USUARIO, USER_ID_DISCORD, NIVEL_ID, EXPERIENCIA, SERVIDOR_ID)"
            sql += (
                " values ('"
                + str(author.name)
                + "', '"
                + str(author.id)
                + "', 1, 0,"
                + str(resultado[0]["id_servidores"])
                + ")"
            )
            try:
                self.pg.update(sql)
                log.info("Usuario " + author.name + " adicionado")
                await self.update_role(author, 0, guild)

            except Exception as e:
                log.error("Erro ao inserir usuario " + str(e))
                raise

    async def update_total_messages(self, message: discord.Message):
        """soma 1 na quantidade de mensagens do usuario"""
        if not self.pg:
            return
        resultado = await self.find_user(message.author.id, message.guild.id)
        if resultado:
            sql = "update usuarios set TOTAL_MENSAGENS = "
            sql += str(int(resultado[0]["total_mensagens"]) + 1)
            sql += " where id_usuarios = " + str(resultado[0]["id_usuarios"])

            self.pg.update(sql)

    async def update(self, message: discord.Message):
        """Atualiza"""
        if not self.pg:
            return
        try:
            result = 0
            # Consulta para buscar informacoes do usuario que enviou a mensagem
            resultado = await self.find_user(message.author.id, message.guild.id)

            # Usuario encontrado
            if resultado:
                # atualiza exp e evolui
                try:
                    result = await self.update_user(
                        resultado, message.author, message.guild
                    )

                except Exception as error:
                    log.error(
                        "Error while connecting to PostgreSQL, %s", error, exc_info=1
                    )
                    pass
            # Usuario nao encontrado, necessario criar
            else:
                await self.insere_usuario(message.guild, message.author)
        except Exception as error:
            log.error("Erro ao buscar o usuario, %s", error, exc_info=1)
        finally:
            return result

    @commands.command(aliases=["exp", "experiencia", "xp"])
    async def experience(self, ctx: commands.Context):
        """Mostra o nivel e experiencia atual"""
        if not self.pg:
            return
        # Consulta para buscar informacoes do usuario que enviou a mensagem
        resultado = await self.find_user(ctx.author.id, ctx.guild.id)
        log.info("Buscando exp do usuario")

        # Tratativa caso não possua avatar
        url = ""
        if ctx.author.avatar and ctx.author.avatar.url:
            url = ctx.author.avatar.url

        # Usuario encontrado
        if resultado:
            experiencia_atual = int(resultado[0]["experiencia"])
            level_atual = str(resultado[0]["nome_nivel"])
            level_atual_num = str(resultado[0]["nivel_id"])
            embed = discord.Embed(colour=0xFA00D4)
            embed.set_author(
                name=ctx.author.name,
                url="https://www.youtube.com/watch?v=Tu5-h4Ye0J0",
                icon_url=url,
            )
            # embed.set_image(url='https://cdn.discordapp.com/attachments/84319995256905728/252292324967710721/embed.png')

            embed.add_field(
                name="Level atual", value=level_atual_num + " - " + level_atual
            )
            embed.add_field(name="Exp atual", value=str(experiencia_atual))
            embed.add_field(
                name="Próximo nível em",
                value=str(
                    int(
                        (await self.prox_nivel(resultado[0]["nivel_id"]))
                        - experiencia_atual
                    )
                ),
            )
            embed.set_footer(
                text=switchGuild(ctx.guild.id),
                icon_url="https://cdn.discordapp.com/avatars/596088044877119507/0d26138b572e7dfffc6cab54073cdb31.webp",
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Usuario não encontrado")


async def setup(bot: commands.Bot):
    """Adiciona cog ao bot"""
    await bot.add_cog(Level(bot))
