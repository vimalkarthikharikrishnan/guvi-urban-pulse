import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()


def get_engine(database=None, **kwargs):
    # database=None means DB_NAME from .env; test_connection.py passes "postgres" to create it
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=database if database is not None else os.environ.get("DB_NAME"),
    )
    return create_engine(url, pool_pre_ping=True, **kwargs)
