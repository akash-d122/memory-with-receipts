from unittest.mock import MagicMock

from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.ingestion.chunking.semantic import SemanticChunker
from memory_with_receipts.ingestion.parsers.base import ParsedDocument, Section


class TestSemanticChunker:
    def test_semantic_split_by_similarity(self) -> None:
        # We will mock the embedding provider to return specific vectors
        # Sentence 1: [1, 0]
        # Sentence 2: [1, 0] (very similar, cosine similarity = 1.0)
        # Sentence 3: [0, 1] (dissimilar, cosine similarity = 0.0)
        provider = MockEmbeddingProvider(dimension=2)
        
        # Override embed to return controlled vectors
        provider.embed = MagicMock(return_value=[
            [1.0, 0.0],  # Sentence 1
            [1.0, 0.0],  # Sentence 2
            [0.0, 1.0],  # Sentence 3
        ])
        
        chunker = SemanticChunker(
            embedding_provider=provider,
            similarity_threshold=0.5,
            max_chunk_tokens=100
        )
        
        content = "First sentence. Second sentence. Third sentence."
        doc = ParsedDocument(
            title="Test Doc",
            content=content,
            sections=[
                Section(
                    title="Section 1",
                    level=1,
                    content=content,
                    start_char=0,
                    end_char=len(content),
                    metadata={"page_number": 2}
                )
            ]
        )
        
        chunks = chunker.chunk(doc)
        
        # Sentence 1 and 2 should group together (sim = 1.0 >= 0.5)
        # Sentence 3 should split into a new chunk (sim = 0.0 < 0.5)
        assert len(chunks) == 2
        assert chunks[0].content == "First sentence. Second sentence."
        assert chunks[1].content == "Third sentence."
        
        # Check that page number and section title mapped correctly
        assert chunks[0].section_title == "Section 1"
        assert chunks[0].page_number == 2
        assert chunks[1].section_title == "Section 1"
        assert chunks[1].page_number == 2
        
        # Check character offsets match content
        assert doc.content[chunks[0].start_char:chunks[0].end_char] == chunks[0].content
        assert doc.content[chunks[1].start_char:chunks[1].end_char] == chunks[1].content

    def test_semantic_split_by_token_limit(self) -> None:
        # All sentences are extremely similar (cosine sim = 1.0)
        provider = MockEmbeddingProvider(dimension=2)
        provider.embed = MagicMock(return_value=[
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ])
        
        # Set max_chunk_tokens to a small limit (e.g. 5 tokens)
        # "Sentence one word." -> ~4 words * 1.33 = ~5.32 tokens
        chunker = SemanticChunker(
            embedding_provider=provider,
            similarity_threshold=0.1,
            max_chunk_tokens=6
        )
        
        content = "Sentence number one. Sentence number two. Sentence number three."
        doc = ParsedDocument(
            title="Test Doc",
            content=content,
            sections=[]
        )
        
        chunks = chunker.chunk(doc)
        
        # Even though they are similar, they must split because of token limits.
        # Each sentence is about 4 words (estimated ~5.3 tokens), so two sentences
        # would be ~10 tokens, exceeding the max limit of 6. Thus, each should split.
        assert len(chunks) == 3
        assert chunks[0].content == "Sentence number one."
        assert chunks[1].content == "Sentence number two."
        assert chunks[2].content == "Sentence number three."

    def test_empty_document_returns_no_chunks(self) -> None:
        provider = MockEmbeddingProvider(dimension=2)
        chunker = SemanticChunker(embedding_provider=provider)
        
        doc = ParsedDocument(title="Empty", content="", sections=[])
        assert chunker.chunk(doc) == []
