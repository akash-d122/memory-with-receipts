"""Domain-specific exceptions for the RAG system.

Each exception maps to a pipeline stage so error handling can be precise
without leaking internal details through the API boundary.
"""


class IngestionError(Exception):
    """Raised when the document ingestion pipeline fails."""


class ParsingError(IngestionError):
    """Raised when a source document cannot be parsed into structured text."""


class ChunkingError(IngestionError):
    """Raised when parsed content cannot be split into valid chunks."""


class EmbeddingError(Exception):
    """Raised when embedding generation fails (provider error, dimension mismatch, etc.)."""


class RetrievalError(Exception):
    """Raised when the retrieval pipeline fails (search, fusion, or ranking)."""


class GenerationError(Exception):
    """Raised when LLM answer generation fails."""


class EvaluationError(Exception):
    """Raised when the evaluation framework encounters an error."""
