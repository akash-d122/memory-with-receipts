"""Pydantic schemas for the document search API (POST /v1/search).

Separate from api/schemas.py which holds operational memory schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for POST /v1/search."""

    query: str = Field(min_length=1, max_length=2000, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum results to return")
    source_type: str | None = Field(default=None, description="Filter by document source_type")
    date_from: datetime | None = Field(default=None, description="Filter: ingested after this date")
    date_to: datetime | None = Field(default=None, description="Filter: ingested before this date")
    metadata_filters: dict[str, Any] | None = Field(
        default=None, description="Simple key-value metadata match"
    )
    enable_vector: bool = Field(default=True, description="Enable vector similarity search")
    enable_keyword: bool = Field(default=True, description="Enable keyword/full-text search")


class SearchResult(BaseModel):
    """A single search result with full receipt metadata."""

    # Chunk identity
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    uri: str | None

    # Chunk content
    chunk_index: int
    content: str
    section_title: str | None
    heading_path: str | None
    start_char: int
    end_char: int

    # Score breakdown
    vector_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float

    # Retrieval metadata
    reason_codes: list[str]
    embedding_provider: str | None = None
    embedding_model: str | None = None


class SearchResponse(BaseModel):
    """Response for POST /v1/search."""

    correlation_id: str
    query: str
    total_results: int
    retrieval_time_ms: float
    results: list[SearchResult]
