"""
Cog com comandos do Reddit: post aleatorio (rr) e top post (tr) do HOT
de um subreddit.

Busca as submissoes recentes via API do PullPush (https://pullpush.io),
que nao exige credenciais nem contorna os bloqueios de bot do Reddit.
"""

import logging
import random
from urllib.parse import quote

import aiohttp
from discord.ext import commands

log = logging.getLogger("reddit")

PULLPUSH_URL = (
    "https://api.pullpush.io/reddit/search/submission/"
    "?subreddit={subreddit}&size=100&sort=desc"
)
REDDIT_BASE = "https://www.reddit.com"


class Reddit(commands.Cog, name="Reddit"):
    """Comandos para buscar posts no Reddit"""

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

    async def _fetch_posts(self, ctx: commands.Context, subreddit: str):
        """Busca as submissoes recentes do subreddit e devolve a lista, ou None."""
        url = PULLPUSH_URL.format(subreddit=quote(subreddit, safe=""))
        log.info("Buscando posts do Reddit: GET %s", url)
        try:
            async with self._get_session().get(url, timeout=15) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error(
                        "Falha ao buscar posts do Reddit: GET %s (status %s): %s",
                        url,
                        resp.status,
                        body[:200],
                    )
                    await ctx.send(
                        f"Nao consegui buscar r/{subreddit} (status {resp.status})."
                    )
                    return None
                data = await resp.json()
        except aiohttp.ClientError as error:
            log.error("Erro ao falar com o Reddit: %s", error)
            await ctx.send("Deu erro ao falar com o Reddit. Tenta de novo?")
            return None

        # Pula posts marcados como SPOILER: o Reddit nao manda embed pra eles
        # no Discord (thumbnail vira "spoiler"), entao nem retornamos.
        posts = [
            post
            for post in data.get("data", [])
            if post.get("permalink") and not post.get("spoiler")
        ]
        if not posts:
            await ctx.send(
                f"Nao achei post nenhum em r/{subreddit}. "
                "Talvez nao exista ou seja privado."
            )
            return None
        return posts

    async def _send_post(self, ctx: commands.Context, post: dict):
        """Envia o link do post; o Discord gera o embed sozinho."""
        title = post.get("title") or "Post"
        url = REDDIT_BASE + post["permalink"]
        await ctx.send(f"**{title}**\n{url}")

    @commands.command()
    async def rr(self, ctx: commands.Context, subreddit: str):
        """Post aleatorio do HOT de um subreddit. Uso: mgy rr <subreddit>"""
        posts = await self._fetch_posts(ctx, subreddit)
        if posts:
            await self._send_post(ctx, random.choice(posts))

    @commands.command(aliases=["top", "tophot"])
    async def tr(self, ctx: commands.Context, subreddit: str):
        """Top post do HOT agora (maior score). Uso: mgy tr <subreddit>"""
        posts = await self._fetch_posts(ctx, subreddit)
        if posts:
            await self._send_post(ctx, max(posts, key=lambda p: p.get("score", 0)))


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Reddit(bot))
