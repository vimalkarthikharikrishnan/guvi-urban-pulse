import os
import re
import sys

from sqlalchemy import text

from db import get_engine

db_name = os.environ.get("DB_NAME", "urban_pulse_db")
if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
    sys.exit(f"Unsafe DB_NAME: {db_name!r}")

try:
    # connect to the default "postgres" database first, so we can create ours if it is missing
    admin = get_engine(database="postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        print("Server version:", conn.execute(text("SHOW server_version")).scalar())
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
        ).scalar()
        if exists:
            print(f"Database {db_name!r} already exists.")
        else:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Created database {db_name!r}.")
    with get_engine(database=db_name).connect() as conn:
        print("Connected to database:", conn.execute(text("SELECT current_database()")).scalar())
    print("OK: connection works.")
except Exception as exc:   # print the error type, never the password
    sys.exit(f"Connection failed: {type(exc).__name__}: {exc}")
