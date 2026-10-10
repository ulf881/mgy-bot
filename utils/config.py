"""Configuracoes compartilhadas do bot (IDs fixos, URLs e limites)."""

import os

# ID do bot (usado apenas como fallback; prefira bot.user.id em runtime)
BOT_ID = 596088044877119507

# Guildas com tratamento especial (macro customizada)
GUILD_MACRO_1 = 1192899104330743998
GUILD_MACRO_2 = 582709300506656792

# Imagem usada nos embeds
AVATAR_URL = (
    "https://cdn.discordapp.com/avatars/"
    "596088044877119507/0d26138b572e7dfffc6cab54073cdb31.webp"
)

# Conteudos especiais (easter eggs) do cog de musica
SPECIAL_TRACK_URL = "https://www.youtube.com/watch?v=Tu5-h4Ye0J0"
GARAGEM_TRACK_URL = "https://www.youtube.com/watch?v=Tu5-h4Ye0J0"
GARAGEM_TITLE = "Quim Barreiros - A garagem da vizinha"
BONUS_ROOM_URL = "https://www.youtube.com/watch?v=8xEJOUfMIHo"
BONUS_ROOM_TITLE = "Bonus Room Blitz - Donkey Kong Country"

# Imagens zoeiras do Max
FROTA_IMAGE_URL = "https://i.imgur.com/dvWqqcz.png"
DROWN_IMAGE_URL = "https://i.imgur.com/dsUPTgY.png"

# Limite maximo de itens que podem ser adicionados de uma vez na fila
MAX_QUEUE = 500

# Intervalo (segundos) entre ganhos de XP por usuario
XP_DELAY_SECONDS = 45


def guild_macro(guild_id: int) -> str:
    """Retorna a macro configurada para a guild (fallback: MGY)."""
    if guild_id == GUILD_MACRO_1:
        return os.environ.get("MACRO", "MGY")
    if guild_id == GUILD_MACRO_2:
        return os.environ.get("MACRO2", "MGY")
    return "MGY"
