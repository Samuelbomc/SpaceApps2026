"""Conexiones cortas con transacciones explícitas y parámetros SQL."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


class Database:
    def __init__(self, url: str):
        self.url = url

    @contextmanager
    def connect(self, *, autocommit=False):
        try:
            with psycopg.connect(
                self.url, connect_timeout=5, row_factory=dict_row, autocommit=autocommit
            ) as connection:
                yield connection
        except (psycopg.OperationalError, psycopg.errors.UndefinedTable):
            raise DatabaseUnavailable(
                "PostgreSQL no está disponible; revisa conexión y migraciones."
            ) from None
