# Local Medical Archive — AI service

Python 3.12, FastAPI (internal port 8001), FastMCP Streamable HTTP (`/mcp` on port 8002), local Ollama, LangGraph, LangChain EnsembleRetriever/RRF, rank_bm25 and embedded persistent ChromaDB. These libraries remain project choices under [specification v1.2](../PROJECT_SPECIFICATION_Local_Medical_Archive_v1.2.md); BM25, hybrid RRF, corrective retrieval, Ollama, Docker and a real MCP endpoint remain required behavior.

## Development

From `ai-service/`:

```sh
uv sync --frozen --group dev --python 3.12
uv run ruff check .
uv run pytest
uv run python -m medical_ai
```

For native execution, point `OLLAMA_BASE_URL` to the local host Ollama and set the storage/source directories appropriately. Compose configures these paths automatically. Internal routes require `X-Internal-Token`; the internal archive listener is separate and not published by Compose.

Configuration: `OLLAMA_BASE_URL` (alias `LLM_BASE_URL`), `LLM_MODEL=qwen3.5:2b`, `EMBEDDING_MODEL=nomic-embed-text`, `INTERNAL_TOKEN` (alias `INTERNAL_API_TOKEN`), `DATA_DIR` (alias `AI_DATA_DIR`), optional `MCP_DEMO_DIR`, `SAMPLE_DOCS_DIR`, `UPLOAD_DIR`. Defaults: `CHUNK_SIZE=900`, `CHUNK_OVERLAP=120`, `RETRIEVAL_K=5`, `MIN_RELEVANT_CHUNKS=1`, `RAG_MAX_CORRECTIVE_RETRIES=2` (maximum 2). Only local Ollama endpoints are accepted. Demo and archive storage must not overlap.

## Parsing, persistence and chunking

Supported medical files are text-layer PDF, TXT and Markdown. Code/JSON/YAML loaders are no longer required or exposed by the medical indexer. Documents are untrusted data and never executable instructions. Scanned, encrypted and malformed PDFs return explicit codes; partial extraction reports missing pages. There is no OCR or cloud fallback.

SQLite stores authoritative chunks and embeddings per corpus; Chroma is repaired from that state after restart and BM25 uses the same rows. Reindexing an unchanged document adds nothing. New text versions/corrections replace that document's chunks; deletion excludes both sparse and vector results. A different embedding model requires fresh index storage.

`MedicalTextSplitter` keeps fitting paragraphs intact, splits longer blocks at table rows, list items and sentence boundaries, and overlaps whole units within the configured budget. A unit longer than the hard limit falls back to words and then characters. Returned chunks are exact substrings. Tests cover result/value/unit, medication/dose, recommendation/deadline and negation near chunk boundaries. No clinical inference or ontology is added. `medical-structure-v1` participates in the indexing fingerprint, so reindexing updates previous splitter output rather than treating it as unchanged.

The supplied v1.2 corpus contains **42 PDF/TXT/MD files, 663711 file bytes**; TXT/MD alone contain 661410 bytes, already exceeding the 512000-byte minimum without PDF overhead. The manifest records source SHA256 and sizes. Text generation uses LF across platforms. Synthetic names, contacts and card identifiers deliberately appear in negative fixtures, including a filename, to test sanitization; they are not real patient data. Reference questions now use retained medical facts such as Cedar's 17-day follow-up, Birch's 6-minute exercise and Maple's 7 mornings rather than identifying record codes.

## Extraction and Corrective RAG

Extraction validates JSON with at most one schema retry. Each fact must match its claimed source page: unsupported quotes and model-generated protocol commands are discarded with explicit incompleteness warnings. Original sources are not rewritten.

Corrective RAG invokes query rewrite, BM25/vector retrieval with RRF, per-chunk model grading, up to two broaden/retrieve retries, then model selection of exact quotes. Final text is assembled from verified excerpts. A valid quotation does not guarantee that the model chose the right dated source; semantic errors and false abstentions remain possible. The app's internal response retains full provenance. Public MCP applies the additional output boundary below.

Ollama decoding is bounded per operation: query 128, grading 256, answer/privacy 1024 and extraction 2048 tokens by default. Responses are validated against JSON schemas. Truncated/malformed output is rejected; RAG returns bounded abstention when evidence cannot be verified, while actual provider outages remain internal 503 errors. Public errors are masked. Extraction defaults to at most 8 facts per batch with a warning at the limit. Settings: `LLM_QUERY_MAX_TOKENS`, `LLM_GRADE_MAX_TOKENS`, `LLM_ANSWER_MAX_TOKENS`, `LLM_EXTRACTION_MAX_TOKENS`, `LLM_PRIVACY_MAX_TOKENS`, `EXTRACTION_MAX_FACTS_PER_BATCH`.

## Public MCP contract

The four tools are a deliberate project choice, fixed to synthetic `mcp_demo`; no public corpus selector or private archive access exists.

| Tool | Behavior |
|---|---|
| `index_folder(path="./sample_docs", glob="**/*")` | Confined medical parsing, structural chunking and embeddings. No generative model. Returns safe counters only; no filenames, paths or raw parser errors |
| `index_status()` | Safe `status`, fixed `corpus`, file/chunk counts and chunk parameters. No timestamps, source list, document content or model calls |
| `find_relevant_docs(query, top_k=5)` | Hybrid RRF retrieval, followed by rules and a local **privacy LLM** over all excerpts. No answer generation, query rewrite or relevance grading |
| `ask_question(question)` | Full Corrective RAG followed by privacy checks over the answer and every returned source excerpt |

`PublicOutput` builds an allowlisted schema rather than forwarding internal dictionaries. Ask returns `responseRef`, `answer`, `sources: [{reference: "S1", text: "..."}]`, `insufficientContext` and `privacy`. Find returns `responseRef`, `chunks: [{reference, text}]` and `privacy`. `privacy.status` is `checked`; warnings are fixed safe categories. Original titles, paths, document/chunk IDs, arbitrary metadata and traces do not leave through MCP.

Each response has a new random `responseRef`; source aliases are scoped to that response. The mapping to actual source metadata is stored locally in `mcp_demo/metadata.sqlite3` (`public_references`) for local evaluation/debugging. `resolve_local` is intentionally absent from the tool registry. The host cannot use `S1` to open the original file through MCP.

All tools and argument/unknown-tool failures are covered by safe error middleware. Privacy/model failure, timeout, malformed output or a direct request for an identifier never enables raw fallback: the public error is `PUBLIC_OUTPUT_UNAVAILABLE: unable to return a checked response.` Requests and provider exceptions are not echoed.

## Shared privacy and manual export

`sanitize_fields` combines deterministic identifier rules, local-model span detection and final deterministic validation. Provider failure, invalid output schema and changes to protected clinical numbers, units, doses, dates or negations block both channels. Public MCP uses `strict=True`: an invalid proposed span (including one absent from the text) or an ambiguous span containing numbers/negation causes a safe refusal. Manual consultation uses `strict=False`: an absent span is ignored, while a numeric/negative possible identifier is left unchanged with a warning requiring manual removal and review. The draft still requires review of the exact content hash before export; this is not a raw fallback on provider failure. Quasi-identifiers can remain, and passing the synthetic suite does not guarantee full anonymity.

Manual consultation uses the same privacy component but remains a separate product flow: local preview → human review of the exact content hash → Copy/Markdown. An edit invalidates review. The archive does not use external AI SDKs or send consultations automatically.

MCP replies automatically to the connected host over its transport. This **is a transfer of the checked synthetic data to that host**, even without an external SDK in our server. It does not authorize access to the personal archive or make the host's later actions local. The standard nginx ingress and fixed host-Ollama proxy are network controls. The optional `compose.llama-cpp.yaml` routes generation to an operator-configured external service through the shim; choosing that mode explicitly changes the inference trust boundary and can send archive source context to that service. See the root README; the default remains local.

## Real evaluation and evidence

Deterministic pytest adapters and genuine Ollama evaluations are separate evidence. Run the latter only on synthetic data with both local models ready. From the repository root, in PowerShell:

```powershell
$env:DATA_DIR = Join-Path $PWD '.local-evaluation/review-qwen35-2b'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:LLM_MODEL = 'qwen3.5:2b'
Remove-Item Env:MCP_DEMO_DIR -ErrorAction SilentlyContinue
& .\ai-service\.venv\Scripts\python.exe scripts/evaluate_public.py --output .local-evaluation/review-qwen35-2b/result.json
```

POSIX equivalent:

```sh
env -u MCP_DEMO_DIR DATA_DIR="$PWD/.local-evaluation/review-qwen35-2b" LLM_MODEL=qwen3.5:2b OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  ai-service/.venv/bin/python scripts/evaluate_public.py --output .local-evaluation/review-qwen35-2b/result.json
```

Use a different `DATA_DIR` and set `CHUNK_SIZE=1400`, `CHUNK_OVERLAP=180` for a comparison. Do not point evaluation storage at the application archive or an existing personal demo override. `--limit 10` checks the first ten cases, not the full suite. The script tests fact retention, source identity (locally), abstention and public privacy separately and stores only checked public payloads; unsuccessful cases and elapsed time remain in the report.

Against the running MCP, from the same root/environment:

```sh
python scripts/mcp_smoke.py --output docs/evaluation/v12-mcp-http-smoke.json
python scripts/host_agent_check.py --output docs/evaluation/v12-host-agent.json
```

The reference host defaults to local Ollama `qwen3.5:4b` for tool calling; prepare it separately or choose `--model`. The main archive defaults to `qwen3.5:2b`. Add `--expect-empty` to MCP smoke after resetting only demo storage. These commands are instructions, not assertions that the latest run passed. Actual status belongs in [VALIDATION](../docs/VALIDATION.md) and [evaluation README](../docs/evaluation/README.md).

Historical v1.1 reports (including `bounded-final-control.json`, 17/21 and first 10/10) used a different corpus/contract and do not certify v1.2 privacy or structural chunking. New evidence uses `v12-*` filenames without overwriting that history.

## Safe demo reset

Stop AI first, then run `uv run python -m medical_ai.reset_demo` with the same configuration, or use the exact Compose commands in the root README. Reset removes only known Chroma/SQLite demo entries, rejects archive overlap/symlink escape and leaves archive originals intact. It is not a replacement for deleting all volumes. Source aliases belong to their original response, so reset also removes their local lookup history.
