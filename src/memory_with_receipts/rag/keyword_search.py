"""Keyword search using Postgres full-text search (tsvector/tsquery).

Falls back to LIKE matching on SQLite for unit test portability.
No GIN index in this phase — uses query-time to_tsvector().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class KeywordSearchResult:
    """A single keyword search result."""

    chunk_id: UUID
    score: float  # ts_rank score on Postgres, 1.0 on SQLite fallback


def keyword_search(
    session: Session,
    query_text: str,
    top_k: int = 10,
    source_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[KeywordSearchResult]:
    """Search for chunks by keyword matching.

    Uses Postgres full-text search (to_tsvector/plainto_tsquery) when
    available, and falls back to LIKE matching on SQLite.

    Args:
        session: SQLAlchemy session.
        query_text: Natural language search query.
        top_k: Maximum results to return.
        source_type: Optional filter by document source_type.
        date_from: Optional filter by document ingested_at >= date_from.
        date_to: Optional filter by document ingested_at <= date_to.
        metadata_filters: Optional key-value filters on document metadata.

    Returns:
        List of KeywordSearchResult sorted by relevance descending.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    if dialect == "postgresql":
        return _pg_keyword_search(
            session, query_text, top_k, source_type, date_from, date_to, metadata_filters,
        )
    return _sqlite_keyword_search(
        session, query_text, top_k, source_type, date_from, date_to, metadata_filters,
    )


def _pg_keyword_search(
    session: Session,
    query_text: str,
    top_k: int,
    source_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    metadata_filters: dict[str, Any] | None,
) -> list[KeywordSearchResult]:
    """Postgres full-text search using tsvector/tsquery."""
    conditions = [
        "to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)"
    ]
    params: dict[str, Any] = {"query": query_text, "top_k": top_k}

    if source_type is not None:
        conditions.append("d.source_type = :source_type")
        params["source_type"] = source_type

    if date_from is not None:
        conditions.append("d.ingested_at >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append("d.ingested_at <= :date_to")
        params["date_to"] = date_to

    if metadata_filters:
        for i, (key, val) in enumerate(metadata_filters.items()):
            param_key = f"meta_key_{i}"
            param_val = f"meta_val_{i}"
            conditions.append(f"d.metadata ->> :{param_key} = :{param_val}")
            params[param_key] = key
            params[param_val] = str(val)

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT c.id AS chunk_id,
               ts_rank(to_tsvector('english', c.content),
                       plainto_tsquery('english', :query)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        {where_clause}
        ORDER BY score DESC
        LIMIT :top_k
    """)

    rows = session.execute(sql, params).fetchall()
    return [KeywordSearchResult(chunk_id=row[0], score=float(row[1])) for row in rows]


def _sqlite_keyword_search(
    session: Session,
    query_text: str,
    top_k: int,
    source_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    metadata_filters: dict[str, Any] | None,
) -> list[KeywordSearchResult]:
    """SQLite fallback using LIKE matching (for unit tests)."""
    words = [w for w in query_text.split() if w.strip()]
    if not words:
        return []

    params: dict[str, Any] = {"top_k": top_k}
    word_conditions = []
    for i, word in enumerate(words):
        param_name = f"pattern_{i}"
        word_conditions.append(f"c.content LIKE :{param_name}")
        params[param_name] = f"%{word}%"

    conditions = ["(" + " OR ".join(word_conditions) + ")"]

    if source_type is not None:
        conditions.append("d.source_type = :source_type")
        params["source_type"] = source_type

    if date_from is not None:
        conditions.append("d.ingested_at >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append("d.ingested_at <= :date_to")
        params["date_to"] = date_to

    if metadata_filters:
        for i, (key, val) in enumerate(metadata_filters.items()):
            param_path = f"meta_path_{i}"
            param_val = f"meta_val_{i}"
            conditions.append(f"json_extract(d.metadata, :{param_path}) = :{param_val}")
            params[param_path] = f"$.{key}"
            params[param_val] = str(val)

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT c.id AS chunk_id,
               1.0 AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        {where_clause}
        LIMIT :top_k
    """)

    rows = session.execute(sql, params).fetchall()
    return [KeywordSearchResult(chunk_id=row[0], score=float(row[1])) for row in rows]

