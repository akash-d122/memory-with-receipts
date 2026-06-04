from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.core.config import Settings


def get_operational_engine(settings: Settings) -> Engine:
    """Create the sync SQLAlchemy engine used by simple operational API endpoints."""
    database_url = settings.database_url
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return create_engine(database_url, future=True)


def get_operational_db_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI dependency for a short-lived sync database session.

    This keeps the first operational API boundary simple. Tests override this dependency with
    an in-memory SQLite session factory.
    """
    if not hasattr(request.app.state, "operational_session_factory"):
        engine = get_operational_engine(request.app.state.settings)
        request.app.state.operational_session_factory = sessionmaker(
            bind=engine, expire_on_commit=False, future=True
        )

    session_factory = request.app.state.operational_session_factory
    with session_factory() as session:
        yield session
