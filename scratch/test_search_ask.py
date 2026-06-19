"""Quick diagnostic: search + ask to validate the full RAG pipeline."""
import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)

# Search for the alert
res = client.post("/v1/search", json={
    "query": "PostgreSQLHighMemoryUsage alert instance memory details",
    "top_k": 5,
})
data = res.json()
total = data["total_results"]
print(f"Search results: {total}")
for i, r in enumerate(data["results"]):
    title = r["document_title"]
    score = r["rrf_score"]
    content_preview = r["content"][:200]
    print(f"  [{i}] {title} (score={score:.4f})")
    print(f"       {content_preview}")
    print()

# Now ask
res2 = client.post("/v1/ask", json={
    "query": "What instance is triggering the PostgreSQLHighMemoryUsage alert and what are its memory details?",
    "top_k": 5,
})
data2 = res2.json()
answer = data2["answer"]
is_insuff = data2["is_insufficient"]
ctx_chunks = data2["context_chunks_used"]
citations = data2["citations"]
print(f"Answer: {answer}")
print(f"Is insufficient: {is_insuff}")
print(f"Context chunks used: {ctx_chunks}")
print(f"Citations count: {len(citations)}")
for c in citations:
    idx = c["citation_index"]
    title = c["document_title"]
    score = c["rrf_score"]
    print(f"  [{idx}] {title} (score={score:.4f})")

client.close()
