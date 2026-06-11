"""Unit tests for build_rag_prompt().

All tests are pure — no DB, no LLM, no Docker required.
"""

from __future__ import annotations

import uuid

from memory_with_receipts.llm.prompts import (
    INSUFFICIENT_CONTEXT_MARKER,
    build_rag_prompt,
)
from memory_with_receipts.rag.search_service import SearchResultData


def _make_chunk(
    content: str = "Test chunk content",
    title: str = "Test Doc",
    source_type: str = "text",
    chunk_index: int = 0,
    section_title: str | None = "Introduction",
) -> SearchResultData:
    """Helper to create minimal SearchResultData for prompt tests."""
    return SearchResultData(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title=title,
        source_type=source_type,
        uri=None,
        chunk_index=chunk_index,
        content=content,
        section_title=section_title,
        heading_path="# Introduction",
        start_char=0,
        end_char=len(content),
        rrf_score=0.5,
    )


class TestBuildRagPromptStructure:
    """Tests for prompt structure and required elements."""

    def test_prompt_contains_question(self) -> None:
        query = "What is the capital of France?"
        prompt = build_rag_prompt(query, [])
        assert query in prompt

    def test_prompt_contains_answer_label(self) -> None:
        prompt = build_rag_prompt("test query", [])
        assert "Answer:" in prompt

    def test_prompt_contains_system_instruction(self) -> None:
        prompt = build_rag_prompt("test", [])
        # System instruction must have citation guidance
        assert "[N]" in prompt or "cite" in prompt.lower()

    def test_prompt_contains_insufficient_context_marker(self) -> None:
        """Prompt must instruct LLM to return the sentinel string."""
        prompt = build_rag_prompt("test", [])
        assert INSUFFICIENT_CONTEXT_MARKER in prompt

    def test_empty_context_produces_no_context_note(self) -> None:
        prompt = build_rag_prompt("test", [])
        assert "no context" in prompt.lower() or "no context available" in prompt.lower()


class TestBuildRagPromptContext:
    """Tests for context chunk formatting."""

    def test_single_chunk_numbered_as_1(self) -> None:
        chunk = _make_chunk(content="PostgreSQL monitoring setup")
        prompt = build_rag_prompt("How to monitor?", [chunk])
        assert "[1]" in prompt
        assert "PostgreSQL monitoring setup" in prompt

    def test_multiple_chunks_numbered_sequentially(self) -> None:
        chunks = [_make_chunk(content=f"Chunk {i}") for i in range(3)]
        prompt = build_rag_prompt("test", chunks)
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "[3]" in prompt
        assert "[4]" not in prompt  # no extra

    def test_chunk_content_appears_in_prompt(self) -> None:
        chunk = _make_chunk(content="Unique sentinel text XYZ987")
        prompt = build_rag_prompt("test", [chunk])
        assert "Unique sentinel text XYZ987" in prompt

    def test_document_title_appears_in_prompt(self) -> None:
        chunk = _make_chunk(title="My Special Document")
        prompt = build_rag_prompt("test", [chunk])
        assert "My Special Document" in prompt

    def test_source_type_appears_in_prompt(self) -> None:
        chunk = _make_chunk(source_type="markdown")
        prompt = build_rag_prompt("test", [chunk])
        assert "markdown" in prompt

    def test_section_title_appears_when_present(self) -> None:
        chunk = _make_chunk(section_title="Deployment Guide")
        prompt = build_rag_prompt("test", [chunk])
        assert "Deployment Guide" in prompt

    def test_prompt_is_string(self) -> None:
        prompt = build_rag_prompt("test", [])
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_is_deterministic(self) -> None:
        chunk = _make_chunk()
        p1 = build_rag_prompt("How?", [chunk])
        p2 = build_rag_prompt("How?", [chunk])
        assert p1 == p2
