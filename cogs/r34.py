"""
Cog com comandos do rule34.xxx: busca a partir de tags e retorna um
resultado aleatorio.

Usa a API oficial (api.rule34.xxx) quando R34_USER_ID/R34_API_KEY estao no
.env. Sem credenciais, raspa as paginas HTML com curl_cffi.

Credenciais em https://rule34.xxx/index.php?page=account&s=options
"""

import logging
import os
import random
import re
from urllib.parse import quote, urlencode, urljoin

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from discord.ext import commands

log = logging.getLogger("r34")

R34_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit=100"
R34_LIST = "https://rule34.xxx/index.php?page=post&s=list&tags={tags}"
R34_BASE = "https://rule34.xxx"

# O Cloudflare do rule34.xxx aceita fingerprint de Chrome e rejeita os demais
# (firefox/edge caem em captcha). As versoes extras servem de fallback.
_IMPERSONATE_TARGETS = ("chrome", "chrome136", "chrome131", "chrome124")

# Estados de busca usados para escolher a mensagem certa ao usuario.
_OK = None
_BLOCKED = "blocked"
_REQUEST_ERROR = "request"


def _sanitize(url: str) -> str:
    """Esconde a api_key antes de logar a URL (privado)."""
    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url)


def _looks_blocked(status_code: int, body: str) -> bool:
    """Detecta o desafio/captcha do Cloudflare em vez de tratar como vazio."""
    if status_code in (403, 429, 503):
        return True
    return "Rule34.xxx CAPTCHA" in body or "cf_chl_opt" in body


def _extract_image(soup: BeautifulSoup) -> str | None:
    """Extrai a URL da imagem do post (absoluta, //host ou relativa)."""
    img = soup.select_one("img#image")
    if img and img.get("src"):
        return urljoin(R34_BASE + "/", img["src"])
    for link in soup.find_all("a", href=True):
        if "original image" in link.get_text(" ", strip=True).lower():
            return urljoin(R34_BASE + "/", link["href"])
    return None


class R34(commands.Cog, name="Rule34"):
    """Comandos para buscar imagens no rule34.xxx (NSFW)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: AsyncSession | None = None

    async def cog_unload(self):
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession()
        return self._session

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
            resp = await self._get_session().get(
                url, impersonate="chrome", timeout=20
            )
        except Exception as error:  # noqa: BLE001
            log.error("rule34 api: falha de conexao: %s", error)
            await ctx.send("Deu erro ao falar com o rule34. Tenta de novo?")
            return None

        if resp.status_code != 200:
            log.error(
                "rule34 api: GET %s (status %s): %s",
                safe_url,
                resp.status_code,
                resp.text[:200],
            )
            await ctx.send("O rule34 respondeu estranho. Tenta de novo?")
            return None

        try:
            results = resp.json()
        except ValueError:
            results = None

        if not isinstance(results, list):
            log.error("rule34 api: resposta inesperada: %s", resp.text[:200])
            if "Missing authentication" in resp.text:
                await ctx.send(
                    "A API do rule34 recusou as credenciais "
                    "(R34_USER_ID/R34_API_KEY)."
                )
            else:
                await ctx.send("O rule34 respondeu estranho. Tenta de novo?")
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

    async def _get(self, session: AsyncSession, url: str):
        """GET tentando fingerprints de Chrome ate um passar pelo Cloudflare."""
        resp = None
        for target in _IMPERSONATE_TARGETS:
            try:
                resp = await session.get(url, impersonate=target, timeout=20)
            except Exception as error:  # noqa: BLE001
                log.warning(
                    "rule34: GET %s falhou com impersonate=%s: %s", url, target, error
                )
                continue
            if not _looks_blocked(resp.status_code, resp.text):
                return resp
            log.warning(
                "rule34: GET %s bloqueado (status %s, impersonate=%s)",
                url,
                resp.status_code,
                target,
            )
        return resp

    async def _find_posts(
        self, session: AsyncSession, query: str
    ) -> tuple[list[str], str | None]:
        """Busca a list page de uma query e devolve ([hrefs], estado).

        estado: None (ok), "blocked" (Cloudflare) ou "request" (outro erro).
        """
        list_url = R34_LIST.format(tags=quote(query, safe="_+"))
        log.info("rule34 scrape: GET %s", list_url)
        resp = await self._get(session, list_url)
        if resp is None:
            return [], _REQUEST_ERROR
        if _looks_blocked(resp.status_code, resp.text):
            log.error(
                "rule34 scrape: GET %s bloqueado (status %s)",
                list_url,
                resp.status_code,
            )
            return [], _BLOCKED
        if resp.status_code != 200:
            log.error("rule34 scrape: GET %s (status %s)", list_url, resp.status_code)
            return [], _REQUEST_ERROR
        soup = BeautifulSoup(resp.text, "html.parser")
        hrefs = [
            urljoin(R34_BASE + "/", post["href"])
            for post in soup.select("span[id^=s] a[href]")
        ]
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
                        "O rule34 bloqueou a busca (Cloudflare). "
                        "Tenta de novo em instantes."
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
            log.info("rule34 scrape: GET %s", href)
            view = await self._get(session, href)
            if view is None or view.status_code != 200:
                log.error(
                    "rule34 scrape: GET %s (status %s)",
                    href,
                    view.status_code if view is not None else "sem resposta",
                )
                if view is not None and _looks_blocked(view.status_code, view.text):
                    await ctx.send(
                        "O rule34 bloqueou o post. Tenta de novo em instantes."
                    )
                else:
                    await ctx.send("Deu erro ao abrir o post. Tenta de novo?")
                return None

            image = _extract_image(BeautifulSoup(view.text, "html.parser"))
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
