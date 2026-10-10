# AGENTS.md

Project-level guide for working in this repository. Tooling and environment
specifics (shell, personal workflow) live in the local `INTRUCTIONS.md`, which is
not committed.

## What this is

MGY Bot is a private Discord bot (Python, `discord.py`) with:

- Music playback (yt-dlp extraction + FFmpeg, Spotify/YouTube search).
- Moderation, leveling/XP, games, Markov text generation, Reddit/rule34,
  Twitch/YouTube/birthday alerts.

User-facing text is **PT-BR**. Commands use the `mgy` prefix. Preserve command
names and aliases unless a change is explicitly requested.

## Stack

- Python >= 3.13, `discord.py[voice]` 2.x, `aiohttp`, `psycopg2`,
  `spotipy`, `google-api-python-client`, `curl-cffi`, `beautifulsoup4`,
  `yt-dlp` (used as a subprocess).
- Postgres accessed through `utils/pgdatabase.py` (thread-safe singleton).
- Dependency/tooling: **uv** (env + lock), **ruff** (lint), **pytest** (tests).

## Layout

```
bot.py                 entry point; loads extensions via setup_hook
cogs/                  max, music, events, level, games, mod, markov,
                       reddit, r34, alerts (alerts is not loaded)
utils/config.py        shared IDs, URLs, limits, guild_macro()
utils/pgdatabase.py    DB singleton (query/update + async aquery/aupdate)
utils/logger.py        logging setup
utils/cmdline.py       banner
tests/                 pytest suite
reports/               project history (progress.md)
```

## Common commands

```text
uv run python bot.py                         # run the bot
uv run ruff check .                          # lint
uv run python -m pytest                      # tests
uv sync                                      # sync env with pyproject/uv.lock
uv add <pkg> / uv add --dev <pkg>            # add dependencies
uv export --format requirements.txt --locked --no-dev --no-hashes --output-file requirements.txt
```

Always use `uv` for Python/deps/tools. Do not invoke bare `python`, `pip`, or
the `.venv` executable directly for project work.

## Conventions

- **SQL**: never build queries with string concatenation; always use `%s`
  parameters. In async code use `await pg.aquery(...)` / `await pg.aupdate(...)`
  so the event loop is not blocked.
- **HTTP**: reuse a per-cog `aiohttp.ClientSession` via a `_get_session()` helper
  and close it in `cog_unload()`.
- **Music state**: per-guild state lives in `Music.players` (`GuildPlayer` with
  separate `current` vs `queue`). Only `_advance_locked`, `_on_track_end`,
  `skip`, `stop`, `limpar`, `verifyalone` mutate the queue.
- **Logging**: module-level `log = logging.getLogger("<Name>")`. Never log
  secrets/tokens.
- **Style**: `ruff` config in `pyproject.toml` (`line-length = 200`,
  select `E, F, W, I`). Keep consistent with surrounding code.
- **Comments/docs**: user-facing strings in PT-BR; code comments only where they
  add value.
- **Validation**: run `uv run ruff check .` and `uv run python -m pytest` after
  changes.

## Environment variables

See `.env.example`. Key vars: `TOKEN`, `DB_HOST` / `DB_USER` / `DB_PASSWORD` /
`DB_NAME`, `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET`, `YOUTUBE_API_KEY`,
`TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET`, `MACRO` / `MACRO2`, `NAME`.

## Gotchas

- FFmpeg must be on `PATH` for voice/music.
- Optional `cookies.txt` (not committed) helps with age-restricted YouTube.
- `mgy restart` pip-installs/updates `yt-dlp` and restarts the process.
- The `alerts` cog needs a DB migration (`usuarios.birthday`,
  `servidores.alert_channel`) and is currently commented out in `bot.py`.
- Keep `yt-dlp` current; extractors break often.
