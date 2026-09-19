# Local Medical Archive — AI service

Python 3.12+, FastAPI (internal port 8001), FastMCP Streamable HTTP (/mcp on port 8002), local Ollama, LangGraph, LangChain EnsembleRetriever RRF, rank_bm25 and embedded persistent ChromaDB.

```sh
uv sync --frozen
uv run ruff check .
uv run pytest
uv run python -m medical_ai
```

Internal routes require X-Internal-Token. Public MCP exposes only index_folder, index_status, find_relevant_docs and ask_question, always bound to synthetic mcp_demo. The internal archive listener is separate and is not published by Compose.

Configuration: OLLAMA_BASE_URL (alias LLM_BASE_URL), LLM_MODEL=qwen2.5:3b, EMBEDDING_MODEL=nomic-embed-text, INTERNAL_TOKEN (alias INTERNAL_API_TOKEN), DATA_DIR (alias AI_DATA_DIR), MCP_DEMO_DIR (optional separate volume), SAMPLE_DOCS_DIR, UPLOAD_DIR. Chunk defaults are CHUNK_SIZE=900, CHUNK_OVERLAP=120, RETRIEVAL_K=5, MIN_RELEVANT_CHUNKS=1, RAG_MAX_CORRECTIVE_RETRIES=2 (maximum 2). Only local Ollama endpoints are accepted.

SQLite stores authoritative chunks and embeddings per corpus. Chroma is repaired from that state after restart; BM25 uses the same rows. Reindexing an unchanged document adds nothing. A new text version/correction replaces that document's chunks, removal excludes both vector and sparse results. Indexing never calls the generative model. A different embedding model requires fresh index storage.

Extraction uses validated JSON with at most one schema retry. Each fact must match its claimed source page: unsupported quotes and model-generated protocol commands are discarded with explicit incompleteness warnings. Scanned, encrypted and malformed PDFs return explicit codes. Partial text extraction reports missing pages. No OCR or cloud fallback exists.

Corrective RAG invokes rewrite, hybrid retrieval, per-chunk model grading, up to two broaden/retrieve retries, then model-based selection of exact quotes. Final text is assembled from verified source excerpts rather than unchecked model paraphrases. See ../docs/evaluation/README.md for actual results and limitations.

Privacy uses deterministic rules, a local model span-detection pass and final deterministic checks over question plus context. It preserves clinical numbers and negations or rejects ambiguous transformations. The app must still require human review before export.

Offline synthetic index reset (stop AI first): uv run python -m medical_ai.reset_demo. It only removes known Chroma/SQLite entries in configured demo storage, rejects archive overlap/symlink escape, and leaves archive data intact. Main Compose instructions are in the root README.




Ollama decoding is bounded per operation (query 128, grading 256, answer/privacy 1024, extraction 2048 tokens).
Each response is strictly validated against its JSON schema. Truncated/malformed output is rejected;
RAG treats it as unverified evidence and returns bounded abstention, while actual provider outages remain 503.
Extraction emits at most 8 facts per batch by default and warns when this limit is reached.
Set LLM_QUERY_MAX_TOKENS, LLM_GRADE_MAX_TOKENS, LLM_ANSWER_MAX_TOKENS,
LLM_EXTRACTION_MAX_TOKENS, LLM_PRIVACY_MAX_TOKENS and EXTRACTION_MAX_FACTS_PER_BATCH to tune within validated limits.
