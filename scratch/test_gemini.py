import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

prompt = """You are a precise question-answering assistant. You are given a question and a numbered list of context passages retrieved from a knowledge base.

Rules:
1. Answer ONLY using information from the provided context passages.
2. Cite every claim with an inline citation marker like [1], [2], etc., where the number matches the context passage number.
3. You may cite multiple passages per claim: [1][3].
4. If the context does not contain enough information to answer the question, respond with exactly one word: INSUFFICIENT_CONTEXT
5. Do NOT invent facts, extrapolate, or use external knowledge.

Context passages:

[1] # Prometheus Alert: PostgreSQLHighMemoryUsage

## Alert Information
- **Alert Name**: PostgreSQLHighMemoryUsage
- **Severity**: warning
- **Instance**: db-replica-02.prod.internal:5432
- **Database**: production_db
- **Timestamp**: 2026-06-17T12:00:00Z
- **Status**: firing
- **Source**: Prometheus Alertmanager

## Alert Summary
Database RAM consumption exceeds 92%

## Alert Description
PostgreSQL RSS size on db-replica-02 is elevated at 58 GB of 64 GB total.
    Source: Prometheus Alert: PostgreSQLHighMemoryUsage | Type: markdown | Chunk: 0

Question: What instance is triggering the PostgreSQLHighMemoryUsage alert and what are its memory details?

Answer:"""

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    print("Response text:", response.text)
except Exception as e:
    print("Error:", e)
