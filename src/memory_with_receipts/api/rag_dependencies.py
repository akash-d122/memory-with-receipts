"""Shared FastAPI dependencies for RAG routes (search and ask).

Centralises the RAG DB session factory so it is not duplicated
across every RAG router module.
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_rag_db_session(request: Request) -> Generator[Session, None, None]:
    """Dependency: short-lived sync DB session for RAG queries.

    Yields one session per request and closes it automatically.
    Tests override this via ``app.dependency_overrides``.
    """
    session_factory = request.app.state.rag_session_factory
    with session_factory() as session:
        yield session
