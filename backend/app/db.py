from collections.abc import Generator
from contextlib import closing
from urllib.parse import urlparse

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    # ponytail: keep the MVP migration in one startup check; add Alembic when schema history is needed.
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS canvas_width INTEGER NOT NULL DEFAULT 8"
        ))
        connection.execute(text(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS canvas_height INTEGER NOT NULL DEFAULT 3"
        ))
        connection.execute(text(
            "ALTER TABLE ports ADD COLUMN IF NOT EXISTS grid_x INTEGER NOT NULL DEFAULT 0"
        ))
        connection.execute(text(
            "ALTER TABLE ports ADD COLUMN IF NOT EXISTS grid_y INTEGER NOT NULL DEFAULT 0"
        ))
        connection.execute(text(
            "UPDATE ports SET grid_x = MOD(position, 8), grid_y = FLOOR(position / 8) "
            "WHERE position > 0 AND grid_x = 0 AND grid_y = 0"
        ))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_ready() -> bool:
    parsed = urlparse(settings.database_url.replace("+psycopg", ""))
    try:
        with closing(
            psycopg.connect(
                dbname=parsed.path.removeprefix("/"),
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port or 5432,
                connect_timeout=2,
            )
        ):
            return True
    except psycopg.Error:
        return False
