"""
Cog com comandos do rule34.xxx: busca a partir de tags e retorna um
resultado aleatorio.

Tenta a API oficial (api.rule34.xxx) quando R34_USER_ID/R34_API_KEY estao
no .env. Sem credenciais, cai num scraping basico das paginas HTML (requer
curl_cffi).

Credenciais em https://rule34.xxx/index.php?page=account&s=options
"""

import logging
import os
import random
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from discord.ext import commands

log = logging.getLogger("r34")

R34_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit=100"
R34_LIST = "https://rule34.xxx/index.php?page=post&s=list&tags={tags}"
R34_BASE = "https://rule34.xxx"


def _sanitize(url: str) -> str:
    """Esconde a api_key antes de logar a URL (privado)."""
    return url.replace("api_key=", "api_key=REDACTED")


class R34(commands.Cog, name="Rule34"):
    """Comandos para buscar imagens no rule34.xxx (NSFW)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(aliases=["rule34"])
    async def r34(self, ctx: commands.Context, *tags: str):
        """Busca no rule34 com as tags dadas e manda um resultado aleatorio.
        Uso: mgy r34 <tags...>"""
        if not tags:
            return await ctx.send("Preciso de ao menos uma tag. Ex.: mgy r34 train")

        if os.environ.get("R34_USER_ID") and os.environ.get("R34_API_KEY"):
            image = await self._api(ctx, tags)
        else:
            image = await self._scrape(ctx, tags)

        if image:
            await ctx.send(image)

    async def _api(self, ctx: commands.Context, tags: tuple[str, ...]) -> str | None:
        """Busca na API oficial (requer credenciais no .env)."""
        params = {
            "tags": " ".join(tags),
            "user_id": os.environ["R34_USER_ID"],
            "api_key": os.environ["R34_API_KEY"],
        }
        url = f"{R34_API}&{urlencode(params)}"
        safe_url = _sanitize(url)
        log.info("rule34 api: GET %s", safe_url)
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=10) as resp,
            ):
                if resp.status != 200:
                    body = await resp.text()
                    log.error(
                        "rule34 api: GET %s (status %s): %s",
                        safe_url,
                        resp.status,
                        body[:200],
                    )
                    await ctx.send("O rule34 respondeu estranho. Tenta de novo?")
                    return None
                results = await resp.json()
        except aiohttp.ClientError as error:
            log.error("rule34 api: falha de conexao: %s", error)
            await ctx.send("Deu erro ao falar com o rule34. Tenta de novo?")
            return None

        if not results:
            await ctx.send("Nada encontrado com essas tags.")
            return None

        post = random.choice(results)
        image = post.get("file_url") or post.get("sample_url")
        if not image:
            await ctx.send("Esse post nao tem imagem.")
            return None
        return image

    async def _find_posts(
        self, session: AsyncSession, query: str
    ) -> tuple[list[str], bool]:
        """Busca a list page de uma query e devolve ([hrefs], bloqueado)."""
        list_url = R34_LIST.format(tags=query)
        log.info("rule34 scrape: GET %s", list_url)
        resp = await session.get(list_url, impersonate="chrome", timeout=20)
        if resp.status_code != 200:
            log.error("rule34 scrape: GET %s (status %s)", list_url, resp.status_code)
            return [], False
        if "CAPTCHA" in resp.text:
            log.error("rule34 scrape: bloqueado por captcha em %s", list_url)
            return [], True
        soup = BeautifulSoup(resp.text, "html.parser")
        hrefs = [
            post["href"] if post["href"].startswith("http") else R34_BASE + post["href"]
            for post in soup.select("span[id^=s] a[href]")
        ]
        return hrefs, False

    async def _scrape(self, ctx: commands.Context, tags: tuple[str, ...]) -> str | None:
        """Fallback basico: raspa as paginas HTML (sem API key)."""
        queries = ["+".join(tags)]
        underscored = "_".join(tags)
        if underscored not in queries:
            queries.append(underscored)

        try:
            async with AsyncSession() as session:
                hrefs: list[str] = []
                blocked = False
                for query in queries:
                    hrefs, blocked = await self._find_posts(session, query)
                    if hrefs or blocked:
                        break

                if not hrefs:
                    if blocked:
                        await ctx.send("O rule34 bloqueou a busca. Tenta de novo?")
                    else:
                        await ctx.send(
                            "Nada encontrado com essas tags. Tags do rule34 usam _ "
                            "(ex.: mgy r34 the_binding_of_isaac)."
                        )
                    return None

                href = random.choice(hrefs)
                log.info("rule34 scrape: GET %s", href)
                view = await session.get(href, impersonate="chrome", timeout=20)
                if view.status_code != 200:
                    log.error(
                        "rule34 scrape: GET %s (status %s)", href, view.status_code
                    )
                    await ctx.send("Deu erro ao abrir o post. Tenta de novo?")
                    return None

                view_soup = BeautifulSoup(view.text, "html.parser")
                full = view_soup.find("a", string="Original image")
                image = None
                if full and full.get("href"):
                    image = full["href"]
                    if image.startswith("/"):
                        image = R34_BASE + image
                if not image:
                    img = view_soup.select_one("img#image")
                    image = img.get("src") if img else None
                if not image:
                    await ctx.send("Esse post nao tem imagem.")
                    return None
                return image
        except Exception as error:  # noqa: BLE001
            log.error("rule34 scrape: erro: %s", error)
            await ctx.send("Deu erro ao falar com o rule34. Tenta de novo?")
            return None


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(R34(bot))
