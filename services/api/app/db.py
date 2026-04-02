from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://synapse:synapse@localhost:55432/synapse")


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
