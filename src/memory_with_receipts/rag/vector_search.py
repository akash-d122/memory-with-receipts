"""Vector similarity search.

For PostgreSQL + pgvector: uses native <=> cosine distance operator.
For SQLite (dev/offline): loads stored embeddings and computes cosine
similarity in-memory via numpy — no pgvector required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import numpy as np
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

    Uses pgvector on PostgreSQL, falls back to in-memory numpy cosine
    similarity on SQLite so the knowledge base works without a running
    Postgres instance.

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
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        return _pg_vector_search(
            session, query_embedding, top_k,
            source_type, date_from, date_to, metadata_filters,
        )
    return _sqlite_vector_search(
        session, query_embedding, top_k,
        source_type, date_from, date_to, metadata_filters,
    )


def _pg_vector_search(
    session: Session,
    query_embedding: list[float],
    top_k: int,
    source_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    metadata_filters: dict[str, Any] | None,
) -> list[VectorSearchResult]:
    """pgvector cosine distance search (PostgreSQL only)."""
    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

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


def _sqlite_vector_search(
    session: Session,
    query_embedding: list[float],
    top_k: int,
    source_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    metadata_filters: dict[str, Any] | None,
) -> list[VectorSearchResult]:
    """In-memory cosine similarity search for SQLite (no pgvector needed).

    Loads all stored embeddings from chunk_embeddings, computes cosine
    similarity against the query vector using numpy, and returns the
    top-k results. Works on the persisted db_runbooks.db without any
    server-side extensions.
    """
    # Build filter conditions for the SQL fetch
    conditions: list[str] = []
    params: dict[str, Any] = {}

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
            conditions.append(
                f"json_extract(d.metadata_, :{param_path}) = :{param_val}"
            )
            params[param_path] = f"$.{key}"
            params[param_val] = str(val)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT ce.chunk_id, ce.embedding
        FROM chunk_embeddings ce
        JOIN chunks c ON c.id = ce.chunk_id
        JOIN documents d ON d.id = c.document_id
        {where_clause}
    """)

    rows = session.execute(sql, params).fetchall()
    if not rows:
        return []

    # Decode stored embeddings.
    # VectorCompat.process_bind_param calls json.dumps(list) → string.
    # SQLite's JSON column then stores that string with extra quoting,
    # so the raw value from a raw SQL query is double-encoded.
    # We need up to two rounds of json.loads to reach the float list.
    chunk_ids: list[Any] = []
    stored_vecs: list[list[float]] = []
    for row in rows:
        raw = row[1]
        try:
            # First decode
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            # Second decode if still a string (double-encoding from VectorCompat)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if not isinstance(parsed, (list, tuple)):
                continue
            chunk_ids.append(row[0])
            stored_vecs.append([float(x) for x in parsed])
        except (ValueError, TypeError):
            continue

    if not stored_vecs:
        return []

    # Compute cosine similarity via numpy
    query_vec = np.array(query_embedding, dtype=np.float32)
    stored_matrix = np.array(stored_vecs, dtype=np.float32)

    # Normalize
    q_norm = np.linalg.norm(query_vec)
    if q_norm == 0:
        return []
    query_vec = query_vec / q_norm

    s_norms = np.linalg.norm(stored_matrix, axis=1, keepdims=True)
    s_norms = np.where(s_norms == 0, 1.0, s_norms)
    stored_matrix = stored_matrix / s_norms

    similarities = stored_matrix @ query_vec  # cosine similarity

    # Get top-k indices
    if len(similarities) <= top_k:
        top_indices = np.argsort(similarities)[::-1]
    else:
        top_indices = np.argpartition(similarities, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

    return [
        VectorSearchResult(
            chunk_id=chunk_ids[int(i)],
            score=float(similarities[int(i)]),
        )
        for i in top_indices
        if similarities[int(i)] > 0
    ]
