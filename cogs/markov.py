# Comando de Markov
# Gera uma mensagem "estilo" de um usuário ou canal com base no historico.
# O modelo e salvo em markov_models e reutilizado enquanto for recente.
# https://towardsdatascience.com/text-generation-with-markov-chains-an-introduction-to-using-markovify-742e6680dc33
import asyncio
import json
import logging
import random
import re
import zlib
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands

from utils.pgdatabase import Postgres

log = logging.getLogger("markov")

# Quantas mensagens (da historia completa) usar para construir um modelo novo.
# Para um usuario o limite e distribuido/coletado por canal ate este total.
MESSAGE_LIMIT = 20000
# Modelo salvo com menos de 30 dias e reutilizado, mais velho e reconstruido.
MODEL_MAX_AGE = timedelta(days=30)
# Tamanho maximo (em palavras) da mensagem gerada.
MAX_GENERATED_WORDS = 50
# Numero de palavras no contexto da cadeia (estado) e versao do formato salvo.
# Subir MODEL_VERSION invalida modelos antigos, forcando a reconstrucao.
STATE_SIZE = 2
MODEL_VERSION = 3


class Markov(commands.Cog):
    """
    Cog com o comando de markov: gera mensagens no "estilo" de um usuario
    ou de um canal a partir do historico de mensagens do servidor.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pg = Postgres()

    @commands.command(hidden=True, aliases=["markov"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def comment(
        self, ctx: commands.Context, target: discord.User | discord.TextChannel = None
    ):
        """
        Gera uma mensagem no estilo de um usuario (@user) ou de um canal (#canal).
        Usa o modelo salvo no banco (markov_models) se ele tiver menos de 30 dias,
        senao constroi um novo a partir do historico.
        Uso: `mgy markov @user` ou `mgy comment #canal`
        """
        if ctx.guild is None:
            await ctx.send("Esse comando so funciona em servidores.")
            return

        resolved = await self._resolve_target(ctx, target)
        if resolved is None:
            return
        target_obj, target_type, label = resolved
        target_id = target_obj.id

        model = await self._load_model(ctx.guild.id, target_id, target_type)
        if model is not None:
            log.info("Reutilizando modelo salvo do target_id=%s", target_id)
        else:
            await ctx.send(f"Buscando o historico e gerando o modelo de {label}...")
            corpus = await self._fetch_corpus(ctx, target_obj, target_type)
            if corpus is None:
                return

            # Construcao e CPU-bound: roda fora do event loop.
            model = await asyncio.to_thread(build_markov_model, corpus)
            if not model:
                await ctx.send(
                    f"Nao foi possivel gerar um modelo com o historico de {label}."
                )
                return

            await self._save_model(ctx.guild.id, target_id, target_type, model)

        generated = generate_markov_text(model, max_length=MAX_GENERATED_WORDS)
        await ctx.send(f"{label}:\n>>> {generated}")

    async def _resolve_target(self, ctx, target):
        """Normaliza o alvo (usuario/canal) em (objeto, tipo, label)."""
        if target is None:
            return ctx.channel, "channel", ctx.channel.mention
        if isinstance(target, (discord.User, discord.Member)):
            return target, "user", f"**{target.display_name}**"
        if isinstance(target, discord.TextChannel):
            return target, "channel", target.mention
        await ctx.send("Alvo invalido. Mencione um @usuario ou #canal.")
        return None

    async def _load_model(self, guild_id: int, target_id: int, target_type: str):
        """
        Busca o modelo salvo no banco. Retorna o modelo se ele existir e for
        recente (menos de MODEL_MAX_AGE), senao retorna None para reconstruir.
        """
        try:
            sql = (
                "SELECT model_data, created_at FROM markov_models "
                "WHERE guild_id = %s AND target_id = %s AND target_type = %s"
            )
            result = await self.pg.aquery(sql, (guild_id, target_id, target_type))
            if not result:
                log.info("Nenhum modelo salvo encontrado para o alvo.")
                return None

            created_at = result[0]["created_at"]
            if datetime.now(UTC) - created_at > MODEL_MAX_AGE:
                log.info("Modelo salvo esta velho demais, reconstruindo.")
                return None

            model = await asyncio.to_thread(
                deserialize_model, result[0]["model_data"]
            )
            if not model:
                log.info("Modelo salvo esta vazio, reconstruindo.")
                return None

            log.info(
                "Reutilizando modelo salvo (criado em %s).",
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            return model
        except Exception as e:  # noqa: BLE001 - cobre erros de query/parse do banco
            log.error("Erro ao carregar modelo do banco: %s", e)
            return None

    async def _fetch_corpus(self, ctx, target, target_type: str):
        """
        Percorre a historia de mensagens do alvo e devolve os textos usados
        para construir o modelo. Retorna None (e envia mensagem de erro) se a
busca falhar ou nao houver mensagens suficientes.
        """
        corpus = []
        scanned = 0

        if target_type == "channel":
            try:
                async for message in target.history():
                    scanned += 1
                    # Ignora apenas bots e mensagens sem texto. Comandos do bot
                    # entram no corpus porque fazem parte do jeito do usuario falar.
                    if not message.content or message.author.bot:
                        continue
                    corpus.append(message.content)
                    if len(corpus) >= MESSAGE_LIMIT:
                        break
            except discord.Forbidden:
                await ctx.send(f"Sem permissao para ler o historico de {target.mention}.")
                return None
            except discord.HTTPException as e:
                log.error("Erro ao buscar historico de %s: %s", target.mention, e)
                await ctx.send(f"Nao foi possivel ler o historico de {target.mention}.")
                return None
        else:
            guild = ctx.guild
            channels = [
                c
                for c in guild.text_channels
                if c.permissions_for(guild.me).read_message_history
            ]
            if not channels:
                await ctx.send(
                    f"Sem permissao para ler o historico de **{target.display_name}**."
                )
                return None

            # Distribui o limite entre os canais. Sem isso, canais no topo da
            # lista (ex: um canal so de quotes) lotam o corpus e os demais
            # (onde o usuario conversa normalmente) nunca sao analisados.
            per_channel = MESSAGE_LIMIT // len(channels) + 1
            channel_stats = {}
            for channel in channels:
                found = 0
                last_id = None
                try:
                    async for message in channel.history():
                        scanned += 1
                        if message.author.id != target.id:
                            continue
                        if not message.content or message.author.bot:
                            continue
                        corpus.append(message.content)
                        found += 1
                        last_id = message.id
                        if found >= per_channel or len(corpus) >= MESSAGE_LIMIT:
                            break
                except discord.HTTPException as e:
                    log.warning("Erro ao buscar historico de %s: %s", channel, e)
                    continue
                channel_stats[channel.id] = (found, last_id)

                if len(corpus) >= MESSAGE_LIMIT:
                    break

            # Se os canais menores tinham poucas mensagens e o total ficou
            # abaixo do limite, volta aos canais cheios (normalmente o canal
            # principal, que e o primeiro) e continua a partir do historico
            # mais antigo ja visto ate completar o orcamento.
            if len(corpus) < MESSAGE_LIMIT:
                for channel in channels:
                    found, last_id = channel_stats.get(channel.id, (None, None))
                    if last_id is None or found < per_channel:
                        continue
                    try:
                        async for message in channel.history(before=last_id):
                            scanned += 1
                            if message.author.id != target.id:
                                continue
                            if not message.content or message.author.bot:
                                continue
                            corpus.append(message.content)
                            if len(corpus) >= MESSAGE_LIMIT:
                                break
                    except discord.HTTPException as e:
                        log.warning(
                            "Erro ao buscar historico mais antigo de %s: %s",
                            channel,
                            e,
                        )
                        continue
                    if len(corpus) >= MESSAGE_LIMIT:
                        break

        if not corpus:
            name = (
                f"**{target.display_name}**"
                if isinstance(target, (discord.User, discord.Member))
                else target.mention
            )
            await ctx.send(f"Nao encontrei mensagens suficientes de {name}.")
            return None

        log.info(
            "Coletadas %s mensagens (de %s analisadas) para o modelo.",
            len(corpus),
            scanned,
        )
        return corpus

    async def _save_model(self, guild_id: int, target_id: int, target_type: str, model):
        """Salva (ou atualiza) o modelo construido na tabela markov_models."""
        serialized = await asyncio.to_thread(serialize_model, model)
        now = datetime.now(UTC)

        sql = (
            "INSERT INTO markov_models (guild_id, target_id, target_type, model_data, created_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (guild_id, target_id, target_type) DO UPDATE "
            "SET model_data = EXCLUDED.model_data, created_at = EXCLUDED.created_at"
        )
        try:
            await self.pg.aupdate(
                sql, (guild_id, target_id, target_type, serialized, now)
            )
            log.info("Modelo salvo no banco de dados.")
        except Exception as e:  # noqa: BLE001 - self.pg.update ja trata erros de conexao
            log.error("Erro ao salvar modelo no banco: %s", e)


# --- Markov Chain Model Implementation ---
#
# O modelo guarda, para cada contexto de STATE_SIZE palavras, as palavras que
# podem vir a seguir. Cada linha/mensagem e envolvida por marcadores de inicio
# (_BEGIN) e fim (_END), entao o texto gerado segue a estrutura das mensagens
# em vez de apenas emendar palavras aleatorias. Tambem guarda o hash das linhas
# originais para evitar recriar mensagens identicas as do historico.

_BEGIN = "\x02"
_END = "\x03"
_KEY_SEP = "\x1f"
# Chave especial do dict do modelo com os hashes das linhas originais.
_LINES_KEY = "source_lines"


def _clean_text(text):
    """Remove URLs, mencoes/emojis do discord e blocos de codigo."""
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"<@!?\d+>|<#\d+>|<a?:\w+:\d+>", "", text)
    text = re.sub(r"`{1,3}.*?`{1,3}", "", text, flags=re.DOTALL)
    return text


def _hash_tokens(tokens):
    """Hash estavel das palavras de uma linha (usado para detectar copias)."""
    return zlib.crc32(_KEY_SEP.join(tokens).encode("utf-8"))


def build_markov_model(text_corpus, state_size=STATE_SIZE):
    """
    Constroi o modelo de Markov a partir de uma lista de mensagens.
    Cada linha de cada mensagem e uma unidade, envolvida por marcadores de
    inicio e fim, para preservar a estrutura (ex: '"frase" fulano, 2020').
    Guarda tambem o hash de cada linha para rejeitar copias na geracao.
    """
    model = {}
    lines = set()
    for raw in text_corpus:
        text = _clean_text(raw)
        for line in text.splitlines():
            tokens = [word.lower() for word in line.split()]
            if not tokens:
                continue
            sequence = [_BEGIN] * state_size + tokens + [_END]
            for i in range(len(sequence) - state_size):
                prefix = tuple(sequence[i:i + state_size])
                model.setdefault(prefix, []).append(sequence[i + state_size])
            lines.add(_hash_tokens(tokens))
    if not model:
        return {}
    model[_LINES_KEY] = frozenset(lines)
    return model


def _generate_once(model, state_size, max_length, keys=None):
    """
    Gera uma sequencia de palavras seguindo a cadeia a partir do inicio.
    Ignora a chave especial _LINES_KEY ao sortear o prefixo inicial.
    """
    if keys is None:
        keys = [key for key in model if isinstance(key, tuple)]
    if not keys:
        return []
    prefix = tuple([_BEGIN] * state_size)
    if prefix not in model:
        prefix = random.choice(keys)
    words = []
    for _ in range(max_length):
        options = model.get(prefix)
        if not options:
            break
        next_word = random.choice(options)
        if next_word == _END:
            break
        words.append(next_word)
        if state_size > 1:
            prefix = tuple(list(prefix[1:]) + [next_word])
        else:
            prefix = (next_word,)
    return words


def generate_markov_text(
    model, max_length=MAX_GENERATED_WORDS, tries=12, min_words=5
):
    """
    Gera um texto a partir do modelo. Faz varias tentativas, descarta copias
    identicas de linhas do historico e escolhe entre as de tamanho razoavel.
    """
    if not model:
        return "Modelo ainda nao tem dados suficientes."
    source_lines = model.get(_LINES_KEY, frozenset())
    keys = [key for key in model if isinstance(key, tuple)]

    candidates = [
        _generate_once(model, STATE_SIZE, max_length, keys) for _ in range(tries)
    ]
    good = [
        words
        for words in candidates
        if len(words) >= min_words and _hash_tokens(words) not in source_lines
    ]
    words = random.choice(good) if good else max(candidates, key=len)

    if not words:
        return "Nao foi possivel gerar nada interessante."

    text = " ".join(words)
    text = text[0].upper() + text[1:]
    if text[-1].isalnum():
        text += "."
    return text


# --- Database Helper Functions ---


def serialize_model(model):
    """
    Serializa o modelo para JSON. As chaves de tupla (word1, word2) viram
    strings separadas por _KEY_SEP. Inclui a versao e os hashes das linhas
    originais para nao reproduzir copias identicas.
    """
    transitions = {k: v for k, v in model.items() if isinstance(k, tuple)}
    data = {
        "version": MODEL_VERSION,
        "state_size": STATE_SIZE,
        "model": {
            _KEY_SEP.join(prefix): next_words
            for prefix, next_words in transitions.items()
        },
        "lines": sorted(model.get(_LINES_KEY, set())),
    }
    return json.dumps(data)


def deserialize_model(json_string):
    """
    Desserializa o modelo do banco. Modelos sem a versao esperada (formato
    antigo) retornam {} para que sejam reconstruidos.
    """
    if not json_string:
        return {}
    try:
        data = json.loads(json_string)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != MODEL_VERSION:
        return {}
    model = {}
    for key, next_words in data.get("model", {}).items():
        model[tuple(key.split(_KEY_SEP))] = next_words
    lines = set(data.get("lines", []))
    if model:
        model[_LINES_KEY] = frozenset(lines)
    return model


async def setup(bot: commands.Bot):
    """Adiciona o cog ao bot"""
    await bot.add_cog(Markov(bot))
