"""RAG prompt builder.

build_rag_prompt() is a pure function — no LLM calls, no DB access.
This makes it trivially testable and lets us inspect the exact prompt
sent to the LLM for auditability.

Context format
--------------
Each chunk is numbered and formatted as:

    [1] <content>
        Source: <document_title> | Type: <source_type> | Chunk: <chunk_index>

The system instruction tells the model to cite using [N] inline and
to respond with INSUFFICIENT_CONTEXT if the context is not enough.
"""

from __future__ import annotations

from memory_with_receipts.rag.search_service import SearchResultData

# Sentinel the model is instructed to return when context is insufficient
INSUFFICIENT_CONTEXT_MARKER = "INSUFFICIENT_CONTEXT"

_SYSTEM_INSTRUCTION = f"""\
You are a precise question-answering assistant. You are given a question and \
a numbered list of context passages retrieved from a knowledge base.

Rules:
1. Answer ONLY using information from the provided context passages.
2. Cite every claim with an inline citation marker like [1], [2], etc., \
where the number matches the context passage number.
3. You may cite multiple passages per claim: [1][3].
4. If the context does not contain enough information to answer the question, \
respond with exactly one word: {INSUFFICIENT_CONTEXT_MARKER}
5. Do NOT invent facts, extrapolate, or use external knowledge.
"""


def build_rag_prompt(
    query: str,
    context_chunks: list[SearchResultData],
) -> str:
    """Build a RAG prompt with numbered, cited context passages.

    Args:
        query: The user's natural-language question.
        context_chunks: Retrieved chunks from SearchService, in rank order.

    Returns:
        Complete prompt string ready to send to a BaseLLMProvider.
        Empty context will produce a prompt that instructs the model to
        return INSUFFICIENT_CONTEXT.
    """
    lines: list[str] = [_SYSTEM_INSTRUCTION, ""]

    if not context_chunks:
        lines.append("Context: (no context available)")
    else:
        lines.append("Context passages:")
        lines.append("")
        for i, chunk in enumerate(context_chunks, start=1):
            lines.append(f"[{i}] {chunk.content}")
            meta_parts = [f"Source: {chunk.document_title}"]
            if chunk.source_type:
                meta_parts.append(f"Type: {chunk.source_type}")
            meta_parts.append(f"Chunk: {chunk.chunk_index}")
            if chunk.section_title:
                meta_parts.append(f"Section: {chunk.section_title}")
            lines.append(f"    {' | '.join(meta_parts)}")
            lines.append("")

    lines.append(f"Question: {query}")
    lines.append("")
    lines.append("Answer:")

    return "\n".join(lines)
