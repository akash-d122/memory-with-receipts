from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from memory_with_receipts.core.config import Settings


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency placeholder.

    Wiring a global session factory belongs in the next DB implementation task.
    """
    raise NotImplementedError(
        "Database session dependency will be wired with migrations in Phase 1."
    )
    yield  # pragma: no cover
