"""Pydantic schemas for POST /v1/ask (answer generation with citations).

Separate from search_schemas.py which holds retrieval-only schemas.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for POST /v1/ask."""

    query: str = Field(min_length=1, max_length=2000, description="Natural language question")
    top_k: int = Field(default=5, ge=1, le=20, description="Context chunks to retrieve")
    source_type: str | None = Field(default=None, description="Filter by document source_type")
    metadata_filters: dict[str, Any] | None = Field(
        default=None, description="Simple key-value metadata match"
    )


class CitationReceiptSchema(BaseModel):
    """Full provenance receipt for a single cited chunk."""

    citation_index: int
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    uri: str | None

    chunk_index: int
    section_title: str | None
    heading_path: str | None
    start_char: int
    end_char: int
    content_snippet: str

    vector_score: float | None
    keyword_score: float | None
    rrf_score: float


class AskResponse(BaseModel):
    """Response for POST /v1/ask."""

    correlation_id: str
    query: str
    answer: str
    is_insufficient: bool
    context_chunks_used: int
    citations: list[CitationReceiptSchema]

    model: str
    provider: str

    retrieval_time_ms: float
    generation_time_ms: float

    # raw_prompt only returned when settings.debug = True
    raw_prompt: str | None = None
