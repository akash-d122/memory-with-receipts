"""Document search service — orchestrates hybrid retrieval with receipts.

Pipeline: embed query → vector search → keyword search → RRF fuse → rerank → build receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import EmbeddingError, RetrievalError
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.rag.fusion import RankedItem, reciprocal_rank_fusion
from memory_with_receipts.rag.keyword_search import keyword_search
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.reranker import BaseReranker, NoOpReranker
from memory_with_receipts.rag.vector_search import vector_search
from memory_with_receipts.retrieval.scoring import score_operational_memories

logger = get_logger(__name__)


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

    def _extract_operational_query(self, session: Session, query_text: str) -> dict[str, Any]:
        """Dynamically extract service, host, category, and severity from query text."""
        from sqlalchemy import select

        from memory_with_receipts.memory.operational_models import EvidenceRecord, SourceRecord

        normalized_query = query_text.lower()

        # 1. Match service name
        services = session.execute(select(SourceRecord.service_name).distinct()).scalars().all()
        matched_service = None
        for service in services:
            if service and service.lower() in normalized_query:
                matched_service = service
                break

        # 2. Match host name
        hosts = session.execute(
            select(SourceRecord.host_name).where(SourceRecord.host_name is not None).distinct()
        ).scalars().all()
        matched_host = None
        for host in hosts:
            if host:
                host_lower = host.lower()
                short_host = host_lower.split(".")[0].split(":")[0]
                if host_lower in normalized_query or short_host in normalized_query:
                    matched_host = host
                    break

        # 3. Match category
        categories = session.execute(
            select(EvidenceRecord.evidence_value)
            .where(EvidenceRecord.evidence_key == "category")
            .distinct()
        ).scalars().all()
        matched_category = None
        for cat in categories:
            if cat and cat.lower() in normalized_query:
                matched_category = cat
                break

        # 4. Match severity
        matched_severity = None
        for sev in ("critical", "warning", "info"):
            if sev in normalized_query:
                matched_severity = sev
                break

        return {
            "service_name": matched_service,
            "host_name": matched_host,
            "category": matched_category,
            "severity": matched_severity,
            "metrics": {},
            "occurred_at": datetime.now(UTC),
        }

    def _map_memory_result_to_search_result(self, result: dict[str, Any]) -> SearchResultData:
        """Map scored operational memory to SearchResultData."""
        memory_id = result["memory_id"]
        memory_key = result["memory_key"]
        summary = result["summary"]
        score = result["score"] / 100.0  # normalize to 0.0 - 1.0 range
        reasons = result["reasons"]

        # Format incident provenance details as clear markdown lists
        provenance_lines = []
        for ref in result.get("provenance", []):
            prov_str = (
                f"- Fired at {ref['occurred_at']} (Severity: {ref['severity']}): "
                f"{ref['evidence_key']}={ref['evidence_value']} "
                f"(Source: {ref['title'] or ref['source_type']})"
            )
            provenance_lines.append(prov_str)

        provenance_text = "\n".join(provenance_lines)
        content = (
            f"Active Alert Summary: {summary}\n"
            f"Incident History / Evidence:\n{provenance_text}"
        )

        return SearchResultData(
            chunk_id=memory_id,
            document_id=memory_id,
            document_title=f"Operational Memory: {memory_key}",
            source_type="operational-memory",
            uri=f"operational-memory://{memory_key}",
            chunk_index=0,
            content=content,
            section_title="Operational Status Summary",
            heading_path=f"Operational Memory > {memory_key}",
            start_char=0,
            end_char=len(content),
            vector_score=score,
            keyword_score=score,
            rrf_score=score,
            reason_codes=reasons,
            embedding_provider="operational-memory-scoring",
            embedding_model="rule-based",
        )

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
        """Execute hybrid search blending documents and operational memories.

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
        # 1. Fetch operational memory results if applicable
        mem_results: list[SearchResultData] = []
        if source_type in (None, "operational-memory"):
            try:
                op_query = self._extract_operational_query(session, query)
                # Check if we matched anything meaningful (service, host, or category)
                if op_query["service_name"] or op_query["host_name"] or op_query["category"]:
                    op_results = score_operational_memories(session, op_query, limit=top_k)
                    mem_results = [
                        self._map_memory_result_to_search_result(r) for r in op_results
                    ]
            except Exception as e:
                logger.error("failed_to_retrieve_operational_memory", error=str(e))

        # 2. Fetch document search results if applicable
        doc_results: list[SearchResultData] = []
        if source_type != "operational-memory":
            if not enable_vector and not enable_keyword:
                doc_results = []
            else:
                try:
                    doc_results = self._execute_search(
                        session, query, top_k, source_type, date_from, date_to,
                        metadata_filters, enable_vector, enable_keyword,
                    )
                except EmbeddingError:
                    raise
                except Exception as e:
                    raise RetrievalError(f"Search failed: {e}") from e

        # 3. Combine and return
        if source_type == "operational-memory":
            return mem_results[:top_k]
        elif source_type is not None:
            # Document-only filter (e.g. "markdown", "pdf")
            return doc_results[:top_k]
        else:
            # Blended: operational memories first (highest context priority), then playbooks
            combined = mem_results + doc_results
            return combined[:top_k]

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
