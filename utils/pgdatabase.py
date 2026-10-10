"""Modulo para acesso ao banco de dados (singleton)."""

import asyncio
import atexit
import logging
import os
import threading

import psycopg2
import psycopg2.extras

log = logging.getLogger("Database")


class Postgres:
    """Inicializa Postgres (singleton).

    A conexao e o cursor do psycopg2 nao sao thread-safe, entao todo acesso e
    serializado por um lock. Use os metodos ``aquery``/``aupdate`` a partir de
    codigo assincrono para nao bloquear o event loop.
    """

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is not None:
            return cls._instance
        with cls._init_lock:
            if cls._instance is not None:
                return cls._instance
            instance = object.__new__(cls)
            instance._db_lock = threading.RLock()
            instance.connection = None
            instance.cursor = None
            if instance._connect():
                cls._instance = instance
            return instance

    def _connect(self) -> bool:
        """Abre a conexao. Retorna True em caso de sucesso."""
        try:
            self.connection = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                dbname=os.getenv("DB_NAME"),
            )
            self.cursor = self.connection.cursor(
                cursor_factory=psycopg2.extras.DictCursor
            )
            self.cursor.execute("SELECT VERSION()")
            db_version = self.cursor.fetchone()
            log.info("Connection established %s", db_version[0])
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error("Error: connection not established %s", e)
            self.connection = None
            self.cursor = None
            return False

    def _ensure_connection(self) -> bool:
        """Garante uma conexao valida, tentando reconectar se necessario."""
        if self.connection is not None and not self.connection.closed:
            return True
        log.warning("Conexao com o banco indisponivel, tentando reconectar")
        Postgres._instance = None
        self.connection = None
        self.cursor = None
        if not self._connect():
            return False
        Postgres._instance = self
        return True

    def _reset(self):
        Postgres._instance = None
        self.connection = None
        self.cursor = None

    def query(self, query: str, params=None):
        """Executa uma query sql e retorna uma lista de dicionarios."""
        if not self._ensure_connection():
            return None

        with self._db_lock:
            try:
                log.debug("Executando query")
                self.cursor.execute(query, params)
                result = self.cursor.fetchall()
                # cuidado com nomes de colunas repetidos
                return [dict(row) for row in result]
            except psycopg2.ProgrammingError as e:
                log.error("Erro ao executar query: %s", e)
                self.connection.rollback()
                return None
            except psycopg2.InterfaceError as e:
                log.error("Conexao perdida: %s", e)
                self._reset()
                return None

    def update(self, query: str, params=None):
        """Executa uma query de escrita e faz commit."""
        if not self._ensure_connection():
            return None

        with self._db_lock:
            try:
                log.debug("Executando update")
                self.cursor.execute(query, params)
            except Exception as error:  # pylint: disable=broad-exception-caught
                log.error("Erro ao executar update: %s", error)
                self.connection.rollback()
                return None
            else:
                self.connection.commit()
                return 1

    async def aquery(self, query: str, params=None):
        """Versao assincrona de :meth:`query` (nao bloqueia o event loop)."""
        return await asyncio.to_thread(self.query, query, params)

    async def aupdate(self, query: str, params=None):
        """Versao assincrona de :meth:`update` (nao bloqueia o event loop)."""
        return await asyncio.to_thread(self.update, query, params)

    def close(self):
        """Fecha cursor e conexao."""
        with self._db_lock:
            for resource in (self.cursor, self.connection):
                try:
                    if resource is not None:
                        resource.close()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            self._reset()


def _shutdown():
    if Postgres._instance is not None:
        Postgres._instance.close()


atexit.register(_shutdown)
