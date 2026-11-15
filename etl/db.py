import os
import config

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_SQLITE = os.path.join(_AQUI, "schema_sqlite.sql")
_SCHEMA_PG = os.path.join(_AQUI, "..", "db", "schema.sql")


def _sqlite() -> bool:
    return config.DATABASE_URL.startswith("sqlite")


def connect():
    url = config.DATABASE_URL
    if url.startswith("sqlite"):
        import sqlite3
        caminho = url.replace("sqlite:///", "", 1)
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        return sqlite3.connect(caminho)
    try:
        import psycopg2
    except ImportError as e:
        raise SystemExit("PostgreSQL pedido em DATABASE_URL, mas falta o driver: pip install psycopg2-binary") from e
    return psycopg2.connect(url)


def init_schema(conn):
    if _sqlite():
        with open(_SCHEMA_SQLITE, encoding="utf-8") as f:
            conn.executescript(f.read())
    else:
        if not os.path.exists(_SCHEMA_PG):
            raise SystemExit(f"Schema do PostgreSQL não encontrado: {_SCHEMA_PG}")
        with open(_SCHEMA_PG, encoding="utf-8") as f, conn.cursor() as cur:
            cur.execute(f.read())
    conn.commit()


def executar(conn, sql, params=()):
    if _sqlite():
        return conn.execute(sql.replace("%s", "?").replace("now()", "CURRENT_TIMESTAMP"), params)
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur
