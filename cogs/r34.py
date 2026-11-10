"""
Cog com comandos do rule34: busca a partir de tags e retorna um resultado
aleatorio.

Usa o espelho rule34.us, que serve o mesmo conteudo do rule34.xxx sem exigir
API key e sem o desafio do Cloudflare. Se o espelho sair do ar ou mudar o
HTML, o scraping precisa ser ajustado.
"""

import logging
import random
import re
from urllib.parse import quote, urljoin

import aiohttp
from bs4 import BeautifulSoup
from discord.ext import commands

log = logging.getLogger("r34")

R34_BASE = "https://rule34.us"
R34_LIST = R34_BASE + "/index.php?r=posts/index&q={tags}"
R34_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
_MEDIA_RE = re.compile(r"\.(?:jpe?g|png|gif|webp|mp4|webm)(?:[?#].*)?$", re.IGNORECASE)

# Estados de busca usados para escolher a mensagem certa ao usuario.
_OK = None
_BLOCKED = "blocked"
_REQUEST_ERROR = "request"


def _looks_blocked(status: int, body: str) -> bool:
    """Detecta bloqueio/challenge em vez de tratar como busca vazia."""
    if status in (403, 429, 503):
        return True
    return (
        "Just a moment" in body
        or "cf_chl_opt" in body
        or "Attention Required" in body
    )


def _extract_image(soup: BeautifulSoup) -> str | None:
    """Extrai a URL do arquivo original do post."""
    video = soup.find("video")
    if video:
        sources = [src["src"] for src in video.find_all("source", src=True)]
        if video.get("src"):
            sources.append(video["src"])
        for src in sources:
            if src.lower().endswith(".mp4"):
                return urljoin(R34_BASE + "/", src)
        if sources:
            return urljoin(R34_BASE + "/", sources[0])

    for link in soup.find_all("a", href=True):
        if _MEDIA_RE.search(link["href"]):
            return urljoin(R34_BASE + "/", link["href"])

    img = soup.select_one("img[src*='/images/']")
    if img and img.get("src"):
        return urljoin(R34_BASE + "/", img["src"])
    return None


class R34(commands.Cog, name="Rule34"):
    """Comandos para buscar imagens no rule34 (NSFW)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_unload(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=R34_HEADERS)
        return self._session

    @commands.command(aliases=["rule34"])
    async def r34(self, ctx: commands.Context, *tags: str):
        """Busca no rule34 com as tags dadas e manda um resultado aleatorio.
        Uso: mgy r34 <tags...>"""
        if not tags:
            return await ctx.send("Preciso de ao menos uma tag. Ex.: mgy r34 train")

        image = await self._scrape(ctx, tags)

        if image:
            await ctx.send(image)

    async def _fetch(
        self, session: aiohttp.ClientSession, url: str
    ) -> tuple[str | None, str | None]:
        """GET e devolve (html, estado): None=ok, "blocked" ou "request"."""
        log.info("rule34: GET %s", url)
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                body = await resp.text()
                if _looks_blocked(resp.status, body):
                    log.error("rule34: GET %s bloqueado (status %s)", url, resp.status)
                    return None, _BLOCKED
                if resp.status != 200:
                    log.error("rule34: GET %s (status %s)", url, resp.status)
                    return None, _REQUEST_ERROR
                return body, _OK
        except (aiohttp.ClientError, TimeoutError) as error:
            log.error("rule34: GET %s erro: %s", url, error)
            return None, _REQUEST_ERROR

    async def _find_posts(
        self, session: aiohttp.ClientSession, query: str
    ) -> tuple[list[str], str | None]:
        """Busca a lista de posts de uma query e devolve ([hrefs], estado)."""
        list_url = R34_LIST.format(tags=quote(query, safe="_+"))
        body, state = await self._fetch(session, list_url)
        if body is None:
            return [], state

        soup = BeautifulSoup(body, "html.parser")
        hrefs: list[str] = []
        seen: set[str] = set()
        for post in soup.select("a[href*='r=posts/view']"):
            href = urljoin(R34_BASE + "/", post["href"])
            if href not in seen:
                seen.add(href)
                hrefs.append(href)
        return hrefs, _OK

    async def _scrape(self, ctx: commands.Context, tags: tuple[str, ...]) -> str | None:
        """Raspa as paginas HTML atras de um resultado aleatorio."""
        queries = ["+".join(tags)]
        underscored = "_".join(tags)
        if underscored not in queries:
            queries.append(underscored)

        try:
            session = self._get_session()
            hrefs: list[str] = []
            state = _OK
            for query in queries:
                hrefs, state = await self._find_posts(session, query)
                if hrefs or state == _BLOCKED:
                    break

            if not hrefs:
                if state == _BLOCKED:
                    await ctx.send(
                        "O rule34 bloqueou a busca. Tenta de novo em instantes."
                    )
                elif state == _REQUEST_ERROR:
                    await ctx.send("Deu erro ao falar com o rule34. Tenta de novo?")
                else:
                    await ctx.send(
                        "Nada encontrado com essas tags. Tags do rule34 usam _ "
                        "(ex.: mgy r34 the_binding_of_isaac)."
                    )
                return None

            href = random.choice(hrefs)
            body, state = await self._fetch(session, href)
            if body is None:
                if state == _BLOCKED:
                    await ctx.send(
                        "O rule34 bloqueou o post. Tenta de novo em instantes."
                    )
                else:
                    await ctx.send("Deu erro ao abrir o post. Tenta de novo?")
                return None

            image = _extract_image(BeautifulSoup(body, "html.parser"))
            if not image:
                await ctx.send("Esse post nao tem imagem.")
                return None
            return image
        except Exception as error:  # noqa: BLE001
            log.error("rule34: erro inesperado: %s", error)
            await ctx.send("Deu erro ao falar com o rule34. Tenta de novo?")
            return None


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(R34(bot))
