"""Verify RAG Pipeline against PostgreSQL DB Operational Data
===========================================================
Queries the RAG pipeline with database alert and runbook questions,
verifying that the system yields accurate answers and traceable receipts
connecting active alert data with the static runbooks.

Usage:
    uv run --env-file .env scripts/verify_rag.py
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memory_with_receipts.core.config import Settings
from memory_with_receipts.embeddings.gemini import GeminiEmbeddingProvider
from memory_with_receipts.embeddings.local import LocalEmbeddingProvider
from memory_with_receipts.llm.gemini import GeminiLLMProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.rag.search_service import SearchService


def run_verification() -> None:
    # Reconfigure stdout to use UTF-8 on Windows to prevent charmap encoding errors
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  RAG Verification - PostgreSQL & Gemini text-embedding-004")
    print("=" * 60)

    settings = Settings()
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        sys.exit(1)

    # 1. Initialize providers
    print("\n[1/3] Initializing LLM and embedding providers...")
    llm_model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
    print(f"      LLM: {llm_model}")
    llm_provider = GeminiLLMProvider(api_key=api_key, model_name=llm_model)

    if settings.embedding_provider == "gemini":
        print(f"      Embeddings: {settings.embedding_model} ({settings.embedding_dimension}-dim)")
        embedding_provider = GeminiEmbeddingProvider(
            api_key=api_key,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    else:
        print(f"      Embeddings: {settings.embedding_model} (local)")
        embedding_provider = LocalEmbeddingProvider(
            model_name=settings.embedding_model
        )

    search_service = SearchService(embedding_provider=embedding_provider)
    generation_service = GenerationService(
        llm_provider=llm_provider,
        search_service=search_service,
        default_top_k=5,
    )

    # 2. Database connection
    db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    print(f"\n[2/3] Connecting to database: {db_url}")
    engine = create_engine(db_url)
    SessionFactory = sessionmaker(bind=engine)

    # 3. Test queries
    test_queries = [
        (
            "What should I do if replication lag on replica instance "
            "db-replica-01.prod.internal:5432 is very high?"
        ),
        (
            "We have an active alert PostgreSQLMaxConnectionsReached. "
            "What diagnostics and runbooks apply?"
        ),
        (
            "Our analytics RDS database has elevated CPU utilization at 98%. "
            "What is the running query causing this and how do we resolve it?"
        )
    ]

    print(f"\n[3/3] Querying RAG system with {len(test_queries)} test cases...")
    print("-" * 60)

    with SessionFactory() as session:
        for idx, query in enumerate(test_queries, 1):
            print(f"\nQUERY {idx}: {query}")
            print("Answer:")
            try:
                result = generation_service.ask(session=session, query=query, top_k=7)
                print(result.answer)
                print("\nCitations:")
                if not result.citations:
                    print("  No citations.")
                for c in result.citations:
                    print(f"  [{c.citation_index}] {c.document_title} (Score: {c.rrf_score:.4f})")
            except Exception as e:
                print(f"  ERROR during query: {e}")
            print("-" * 60)


if __name__ == "__main__":
    run_verification()
