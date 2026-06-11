import getpass
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.local import LocalEmbeddingProvider
from memory_with_receipts.llm.gemini import GeminiLLMProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService


def setup_db() -> sessionmaker:
    """Sets up an in-memory SQLite database and creates the schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_document(
    session: Session,
    embedding_provider: LocalEmbeddingProvider,
    title: str,
    content: str,
) -> None:
    """Seeds a test document and its embedded chunk into the DB."""
    doc = Document(
        id=uuid.uuid4(),
        title=title,
        source_type="text",
        content_hash=Document.compute_content_hash(content + str(uuid.uuid4())),
        raw_content_text=content,
        content_size_bytes=len(content.encode()),
        metadata_={},
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content=content,
        content_hash=Document.compute_content_hash(content),
        section_title="Introduction",
        heading_path="# Introduction",
        start_char=0,
        end_char=len(content),
        token_count=len(content.split()),
        metadata_={},
    )
    session.add(chunk)
    session.flush()

    vector = embedding_provider.embed_single(content)
    emb = ChunkEmbedding(
        id=uuid.uuid4(),
        chunk_id=chunk.id,
        embedding=vector,
        embedding_model=embedding_provider.model_name,
        embedding_dimension=embedding_provider.dimension,
        embedding_provider=embedding_provider.provider_name,
        embedded_at=datetime.now(UTC),
    )
    session.add(emb)
    session.commit()
    print(f"Seeded document '{title}'.")


def main() -> None:
    print("=== Manual Real-Time LLM Test ===")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        api_key = getpass.getpass("Enter your Gemini API Key: ")
    
    if not api_key:
        print("API Key is required to test real LLM.", file=sys.stderr)
        sys.exit(1)

    print("\nInitializing GeminiLLMProvider...")
    try:
        llm_provider = GeminiLLMProvider(api_key=api_key, model_name="gemini-3.5-flash")
    except Exception as e:
        print(f"Failed to initialize Gemini: {e}")
        sys.exit(1)

    print("Initializing LocalEmbeddingProvider (this may download the model)...")
    embedding_provider = LocalEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    print("Setting up SearchService and GenerationService...")
    search_service = SearchService(embedding_provider=embedding_provider)
    generation_service = GenerationService(
        llm_provider=llm_provider,
        search_service=search_service,
        default_top_k=3,
    )

    print("Setting up In-Memory SQLite Database...")
    SessionFactory = setup_db()

    with SessionFactory() as session:
        print("\n--- Seeding Knowledge Base ---")
        seed_document(
            session,
            embedding_provider,
            "Internal Wiki: Kubernetes Setup",
            (
                "Our Kubernetes clusters are managed via Terraform. We use autoscaling groups "
                "with a minimum of 3 nodes and a maximum of 10 nodes. To deploy a new service, "
                "you must create a Helm chart in the 'charts' directory and trigger the "
                "GitHub Actions workflow."
            ),
        )
        seed_document(
            session,
            embedding_provider,
            "Internal Wiki: Database Access",
            (
                "Production database access is strictly regulated. Developers cannot access "
                "production directly. You must use the Teleport proxy service and request "
                "temporary read-only credentials via the Slack #ops-requests channel. "
                "The proxy URL is db-proxy.internal.company.com."
            ),
        )

        print("\n--- Real-Time Query Mode ---")
        print("Type 'exit' or 'quit' to stop.\n")

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
                result = generation_service.ask(session=session, query=query, top_k=3)
            except Exception as e:
                print(f"Error during generation: {e}\n")
                continue

            print(f"\n[{result.model} | {result.provider}]")
            print(f"Retrieval Time:  {result.retrieval_time_ms} ms")
            print(f"Generation Time: {result.generation_time_ms} ms")
            if result.input_tokens is not None:
                print(f"Tokens:          {result.input_tokens} in / {result.output_tokens} out")
            print("-" * 40)
            print(f"Answer:\n{result.answer}")
            print("-" * 40)
            
            if result.is_insufficient:
                print("Status: INSUFFICIENT CONTEXT")
            else:
                print("Citations Found:")
                if not result.citations:
                    print(
                        "  None (LLM failed to follow citation instructions "
                        "or context wasn't used)."
                    )
                for c in result.citations:
                    print(f"  [{c.citation_index}] Document: {c.document_title}")
                    print(f"      Score: {c.rrf_score:.3f}")
                    print(f"      Snippet: {c.content_snippet[:80]}...")
            print("\n")


if __name__ == "__main__":
    main()
