"""Shared database helper (PostgreSQL). Credentials come from environment variables / .env only."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()


def get_engine(database: str | None = None, **kwargs):
    """Build a SQLAlchemy engine from .env.

    database=None uses DB_NAME; pass database="postgres" to connect to the maintenance DB
    (needed to create DB_NAME the first time).
    """
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=database if database is not None else os.environ.get("DB_NAME"),
    )
    return create_engine(url, pool_pre_ping=True, **kwargs)
