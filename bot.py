"""
    Bot MGY para discord, toca musica e zoa com o max
"""
import sys
import asyncio
import logging
import discord
from discord.ext import commands
from utils import logger, __program__  # pylint: disable=unused-import # noqa: F401
from utils.cmdline import banner
from utils.pgdatabase import Postgres
import os
from dotenv import load_dotenv

load_dotenv(override=True)


def get_prefix(client, message):
    """Prepara prefixos para chamada do bot"""

    prefixes = [
        "mgy ",
        "MGY ",
        "Mgy ",
        "MgY ",
        "MGy ",
        "mGY ",
        "mgY ",
        "mGy ",
        "mgy",
        "MGY",
        "Mgy",
        "MgY",
        "MGy",
        "mGY",
        "mgY",
        "mGy",
    ]

    # Allow users to @mention the bot instead of using a prefix when using a command. Also optional
    return commands.when_mentioned_or(*prefixes)(client, message)


# Below cogs represents our folder our cogs are in.
INITIAL_EXTENSIONS = [
    "cogs.max",
    "cogs.music",
    "cogs.events",
    "cogs.level",
    "cogs.games",
    "cogs.mod",
]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=get_prefix,
    case_insensitive=True,
    description="Max Gay Yeah!",
    intents=intents,
)

bot.game = False  # Variavel para verificar se esta ingame
bot.acoes = []  # Acoes para jogo
bot.total_mensagem = 0
bot.pg = Postgres()  # Instancia unica do Postgres
bot.bonusXP = False

log = logging.getLogger("main")


# after using async_with
async def main():
    """Main"""

    log.debug(
        "##################### Iniciando %s #########################", __program__
    )

    banner()

    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.critical("Failed to load extensions {extensions}. %s", e, exc_info=True)
            sys.exit()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    loop.close()


@bot.event
async def on_ready():
    """http://discordpy.readthedocs.io/en/rewrite/api.html#discord.on_ready"""
    log.info(
        "\n\nLogged in as: %s - %s\nVersion: %s\n",
        bot.user.name,
        bot.user.id,
        discord.__version__,
    )

    # for guild in bot.guilds:
    #     print(guild.id)

    # Changes Playing Status. type=1(streaming) for a standard game you could remove type and url.
    await bot.change_presence(activity=discord.Game(name=os.environ["NAME"], type=1))
    log.info("Successfully logged in and booted...!")


bot.run(os.environ["TOKEN"], reconnect=True)
