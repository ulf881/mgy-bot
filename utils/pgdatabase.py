""" Modulo para acesso ao banco de dados """
import os
import logging
import psycopg2
import psycopg2.extras

log = logging.getLogger("Database")


class Postgres(object):
    """Inicializa Postgres (singleton)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)

            try:
                connection = Postgres._instance.connection = psycopg2.connect(
                    host=os.getenv("DB_HOST"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    dbname=os.getenv("DB_NAME"),
                )
                cursor = Postgres._instance.cursor = connection.cursor(
                    cursor_factory=psycopg2.extras.DictCursor
                )
                cursor.execute("SELECT VERSION()")
                db_version = cursor.fetchone()
                log.info("Connection established %s\n", db_version[0])

            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error("Error: connection not established %s", e, exc_info=1)
                Postgres._instance = None

        return cls._instance

    def __init__(self):
        self.connection: psycopg2.extras.DictConnection = self._instance.connection
        self.cursor: psycopg2.extras.DictCursor = self._instance.cursor

    def query(self, query: str):
        """Executa uma query sql e retorna um dicionario"""
        try:
            log.info("Executando: %s", query)
            self.cursor.execute(query)
            result = self.cursor.fetchall()

            # prepara uma lista de dicionarios, cuidado com nomes de colunas repetidos
            dict_result = []
            for row in result:
                dict_result.append(dict(row))

        except psycopg2.ProgrammingError as e:
            log.error("error execting query, error: %s", e, exc_info=1)
            self.connection.rollback()
            return None
        except psycopg2.InterfaceError as e:
            log.error("Error: connection not established %s", e, exc_info=1)
            _instance = None  # noqa: F841
            Postgres()
        else:
            return dict_result

    def update(self, query):
        """Executa uma query sql e retorna um dicionario"""
        try:
            log.info("Executando: %s", query)
            self.cursor.execute(query)

        except Exception as error:  # pylint: disable=broad-exception-caught
            log.error("error execting query, error: %s", error, exc_info=1)
            self.connection.rollback()
            return None
        else:
            self.connection.commit()
            return 1

    def __del__(self):
        log.info("Encerrando connection e cursor ")
        self.connection.close()
        self.cursor.close()
