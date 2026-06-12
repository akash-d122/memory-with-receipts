"""Document search service — orchestrates hybrid retrieval with receipts.

Pipeline: embed query → vector search → keyword search → RRF fuse → rerank → build receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import EmbeddingError, RetrievalError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.rag.fusion import RankedItem, reciprocal_rank_fusion
from memory_with_receipts.rag.keyword_search import keyword_search
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.reranker import BaseReranker, NoOpReranker
from memory_with_receipts.rag.vector_search import vector_search


@dataclass
class SearchResultData:
    """Internal search result with full receipt metadata."""

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
    rrf_score: float = 0.0

    # Retrieval metadata
    reason_codes: list[str] = field(default_factory=list)
    embedding_provider: str | None = None
    embedding_model: str | None = None


class SearchService:
    """Orchestrates document RAG hybrid retrieval.

    Args:
        embedding_provider: Provider to embed query text.
        reranker: Optional reranker (defaults to NoOpReranker).
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        reranker: BaseReranker | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._reranker = reranker or NoOpReranker()

    def search(
        self,
        session: Session,
        query: str,
        top_k: int = 10,
        source_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        metadata_filters: dict[str, Any] | None = None,
        enable_vector: bool = True,
        enable_keyword: bool = True,
    ) -> list[SearchResultData]:
        """Execute hybrid search and return receipt-backed results.

        Args:
            session: SQLAlchemy session.
            query: Natural language search query.
            top_k: Maximum results to return.
            source_type: Filter by document source_type.
            date_from: Filter documents ingested after this date.
            date_to: Filter documents ingested before this date.
            metadata_filters: Simple key-value metadata match.
            enable_vector: Toggle vector similarity search.
            enable_keyword: Toggle keyword/full-text search.

        Returns:
            List of SearchResultData with full receipt metadata.

        Raises:
            RetrievalError: If search fails.
            EmbeddingError: If query embedding fails or dimension mismatch.
        """
        if not enable_vector and not enable_keyword:
            return []

        try:
            return self._execute_search(
                session, query, top_k, source_type, date_from, date_to,
                metadata_filters, enable_vector, enable_keyword,
            )
        except EmbeddingError:
            raise
        except Exception as e:
            raise RetrievalError(f"Search failed: {e}") from e

    def _execute_search(
        self,
        session: Session,
        query: str,
        top_k: int,
        source_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        metadata_filters: dict[str, Any] | None,
        enable_vector: bool,
        enable_keyword: bool,
    ) -> list[SearchResultData]:
        """Internal search execution."""
        filter_kwargs = {
            "source_type": source_type,
            "date_from": date_from,
            "date_to": date_to,
            "metadata_filters": metadata_filters,
        }

        # 1. Vector search
        vector_items: list[RankedItem] = []
        if enable_vector:
            query_embedding = self._embedding_provider.embed_single(query)
            self._embedding_provider.validate_dimension(query_embedding)

            v_results = vector_search(
                session, query_embedding, top_k=top_k * 2, **filter_kwargs,
            )
            vector_items = [
                RankedItem(chunk_id=r.chunk_id, score=r.score) for r in v_results
            ]

        # 2. Keyword search
        keyword_items: list[RankedItem] = []
        if enable_keyword:
            k_results = keyword_search(
                session, query, top_k=top_k * 2, **filter_kwargs,
            )
            keyword_items = [
                RankedItem(chunk_id=r.chunk_id, score=r.score) for r in k_results
            ]

        # 3. RRF fusion
        fused = reciprocal_rank_fusion(vector_items, keyword_items)

        if not fused:
            return []

        # 4. Hydrate top candidates (e.g. up to top_k * 2) to get content for reranking
        candidates = fused[: top_k * 2]
        chunk_ids = [f.chunk_id for f in candidates]
        hydrated = self._build_receipts(session, candidates, chunk_ids)

        # 5. Rerank hydrated SearchResultData objects
        reranked = self._reranker.rerank(query, hydrated)

        # 6. Truncate to top_k
        return reranked[:top_k]

    def _build_receipts(
        self,
        session: Session,
        fused_results: list,
        chunk_ids: list[UUID],
    ) -> list[SearchResultData]:
        """Load chunk + document + embedding metadata and build receipt results."""
        # Load chunks with their documents and embeddings
        chunks = (
            session.query(Chunk)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )

        chunk_map: dict[str, Chunk] = {str(c.id): c for c in chunks}

        # Load embedding metadata for these chunks
        embeddings = (
            session.query(ChunkEmbedding)
            .filter(ChunkEmbedding.chunk_id.in_(chunk_ids))
            .all()
        )
        embedding_map: dict[str, ChunkEmbedding] = {}
        for emb in embeddings:
            # Keep the first (most recent could be tracked, but one per chunk for now)
            if str(emb.chunk_id) not in embedding_map:
                embedding_map[str(emb.chunk_id)] = emb

        results: list[SearchResultData] = []
        for fused in fused_results:
            chunk_id_str = str(fused.chunk_id)
            chunk = chunk_map.get(chunk_id_str)
            if chunk is None:
                continue  # Orphaned embedding, skip

            doc: Document = chunk.document
            emb = embedding_map.get(chunk_id_str)

            results.append(SearchResultData(
                chunk_id=chunk_id_str,
                document_id=str(doc.id),
                document_title=doc.title,
                source_type=doc.source_type,
                uri=doc.uri,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                vector_score=fused.vector_score,
                keyword_score=fused.keyword_score,
                rrf_score=fused.rrf_score,
                reason_codes=fused.reason_codes,
                embedding_provider=emb.embedding_provider if emb else None,
                embedding_model=emb.embedding_model if emb else None,
            ))

        return results
