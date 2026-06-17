"""Manual real-time test against the ingested DB runbooks knowledge base.

Uses the db_runbooks.db SQLite database populated by:
    uv run scripts/ingest_db_runbooks.py

Run with:
    uv run --env-file .env manual_test.py
"""

import getpass
import os
import sys

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from memory_with_receipts.core.config import Settings
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.gemini import GeminiEmbeddingProvider
from memory_with_receipts.embeddings.local import LocalEmbeddingProvider
from memory_with_receipts.llm.gemini import GeminiLLMProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.rag.models import Chunk, Document
from memory_with_receipts.rag.search_service import SearchService

DB_PATH = "sqlite:///db_runbooks.db"


def print_kb_stats(session) -> None:
    """Print a summary of the ingested knowledge base."""
    doc_count = session.query(func.count(Document.id)).scalar()
    chunk_count = session.query(func.count(Chunk.id)).scalar()
    print(f"  Knowledge Base : {doc_count} documents, {chunk_count} chunks")
    if doc_count > 0:
        print("\n  Sample documents:")
        for doc in session.query(Document).limit(5).all():
            print(f"    - {doc.title}")
        if doc_count > 5:
            print(f"    ... and {doc_count - 5} more")


def main() -> None:
    print("=" * 60)
    print("  DB Runbooks RAG - Interactive Query Mode")
    print("=" * 60)

    # ------------------------------------------------------------------
    # API key
    # ------------------------------------------------------------------
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        api_key = getpass.getpass("Enter your Gemini API Key: ")
    if not api_key:
        print("API Key is required.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Initialize providers
    # ------------------------------------------------------------------
    # Model selection: prefer env var, fall back to gemini-1.5-flash
    model_name = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
    print(f"\nInitializing GeminiLLMProvider (model: {model_name})...")
    try:
        llm_provider = GeminiLLMProvider(api_key=api_key, model_name=model_name)
    except Exception as e:
        print(f"Failed to initialize Gemini: {e}")
        sys.exit(1)

    settings = Settings()
    if settings.embedding_provider == "gemini":
        print("Initializing GeminiEmbeddingProvider...")
        embedding_provider = GeminiEmbeddingProvider(
            api_key=api_key,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    else:
        print("Initializing LocalEmbeddingProvider...")
        embedding_provider = LocalEmbeddingProvider(
            model_name=settings.embedding_model
        )

    print("Setting up SearchService and GenerationService...")
    search_service = SearchService(embedding_provider=embedding_provider)
    generation_service = GenerationService(
        llm_provider=llm_provider,
        search_service=search_service,
        default_top_k=5,
    )

    # ------------------------------------------------------------------
    # Connect to the persisted knowledge base
    # ------------------------------------------------------------------
    db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    print(f"\nConnecting to knowledge base: {db_url}")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)

    with SessionFactory() as session:
        print_kb_stats(session)

        doc_count = session.query(func.count(Document.id)).scalar()
        if doc_count == 0:
            print(
                "\n[WARNING] Knowledge base is empty!\n"
                "Run first:  uv run --env-file .env "
                "scripts/ingest_db_runbooks.py"
            )
            sys.exit(1)

        print("\n" + "-" * 60)
        print("  Real-Time Query Mode")
        print("  Type 'exit' or 'quit' to stop.")
        print("  Example queries:")
        print("    - What should I do when RDS disk space is critical?")
        print("    - How do I diagnose a PostgreSQL deadlock?")
        print("    - What causes replication lag and how to fix it?")
        print("    - How do I handle too many connections in PostgreSQL?")
        print("    - What is the 23505 error in PostgreSQL?")
        print("-" * 60 + "\n")

        while True:
            try:
                query = input("Ask a question: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if query.lower() in ("exit", "quit"):
                break
            if not query:
                continue

            print("\nGenerating answer...")
            try:
                result = generation_service.ask(
                    session=session, query=query, top_k=5
                )
            except Exception as e:
                print(f"Error during generation: {e}\n")
                continue

            print(f"\n[{result.model} | {result.provider}]")
            print(f"Retrieval Time:  {result.retrieval_time_ms} ms")
            print(f"Generation Time: {result.generation_time_ms} ms")
            if result.input_tokens is not None:
                tokens = f"{result.input_tokens} in / {result.output_tokens} out"
                print(f"Tokens:          {tokens}")
            print("-" * 60)
            print(f"Answer:\n{result.answer}")
            print("-" * 60)

            if result.is_insufficient:
                print("Status: INSUFFICIENT CONTEXT")
            else:
                print("Citations Found:")
                if not result.citations:
                    print(
                        "  None (LLM failed to follow citation "
                        "instructions or context was not used)."
                    )
                for c in result.citations:
                    print(f"  [{c.citation_index}] {c.document_title}")
                    print(f"      Score: {c.rrf_score:.4f}")
                    snippet = c.content_snippet[:100]
                    print(f"      Snippet: {snippet}...")
            print("\n")


if __name__ == "__main__":
    main()
