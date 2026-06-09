"""Vector similarity search using pgvector cosine distance.

Queries chunk_embeddings via raw SQL to compute cosine similarity.
Uses CAST(:qvec AS vector) to avoid psycopg :: parameter conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class VectorSearchResult:
    """A single vector search result."""

    chunk_id: UUID
    score: float  # cosine similarity (1 - distance), higher is better


def vector_search(
    session: Session,
    query_embedding: list[float],
    top_k: int = 10,
    source_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[VectorSearchResult]:
    """Search for chunks by vector similarity.

    Args:
        session: SQLAlchemy session.
        query_embedding: Query vector (must match embedding dimension).
        top_k: Maximum results to return.
        source_type: Optional filter by document source_type.
        date_from: Optional filter by document ingested_at >= date_from.
        date_to: Optional filter by document ingested_at <= date_to.
        metadata_filters: Optional key-value filters on document metadata.

    Returns:
        List of VectorSearchResult sorted by similarity descending.
    """
    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Build WHERE clauses
    conditions: list[str] = []
    params: dict[str, Any] = {"query_vec": query_vec_str, "top_k": top_k}

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

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT ce.chunk_id,
               1 - (ce.embedding <=> CAST(:query_vec AS vector)) AS score
        FROM chunk_embeddings ce
        JOIN chunks c ON c.id = ce.chunk_id
        JOIN documents d ON d.id = c.document_id
        {where_clause}
        ORDER BY ce.embedding <=> CAST(:query_vec AS vector) ASC
        LIMIT :top_k
    """)

    rows = session.execute(sql, params).fetchall()
    return [VectorSearchResult(chunk_id=row[0], score=float(row[1])) for row in rows]
