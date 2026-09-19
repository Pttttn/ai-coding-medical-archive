import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from .config import Settings
from .errors import ServiceError
from .extraction import PROMPT_VERSION, SCHEMA_VERSION, extract
from .external_output import PublicOutput, PublicToolErrors
from .indexer import Corpus, source_of
from .ollama import Ollama
from .parsing import PARSER_VERSION, confined_path, parse_file
from .privacy import consultation
from .rag import CorrectiveRAG
from .schemas import AskRequest, ConsultationRequest, IndexRequest, Page, ProcessRequest, RemoveRequest


class Services:
    def __init__(self, settings: Settings, provider=None):
        self.settings = settings
        self.provider = provider or Ollama(settings)
        self.archive = Corpus("archive", settings, self.provider)
        self.demo = Corpus("mcp_demo", settings, self.provider)
        self.archive_rag = CorrectiveRAG(self.archive, self.provider, settings)
        self.demo_rag = CorrectiveRAG(self.demo, self.provider, settings)
        self.public_output = PublicOutput(self.demo, self.provider)


@lru_cache
def get_services():
    return Services(Settings())


def create_app(services: Services | None = None) -> FastAPI:
    services = services or get_services()
    app = FastAPI(title="Local Medical Archive — internal AI", version="0.1.0")

    def authorize(x_internal_token: Annotated[str | None, Header()] = None):
        if not x_internal_token or not secrets.compare_digest(x_internal_token, services.settings.internal_token):
            raise ServiceError("UNAUTHORIZED", "Требуется внутренний токен.", 401)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, "message": exc.message}})

    @app.get("/health")
    def health():
        return {"status": "running", **services.provider.health(), "promptVersion": PROMPT_VERSION,
                "schemaVersion": SCHEMA_VERSION, "parserVersion": PARSER_VERSION}

    @app.post("/internal/process", dependencies=[Depends(authorize)])
    def process(body: ProcessRequest):
        if (body.text is None) == (body.filePath is None):
            raise ServiceError("INVALID_INPUT", "Укажите ровно одно из text и filePath.")
        warnings = []
        if body.filePath is not None:
            path = confined_path(body.filePath, services.settings.upload_dir)
            if not path.is_file():
                raise ServiceError("FILE_NOT_FOUND", "Исходный файл не найден.", 404)
            text, pages, warnings = parse_file(path, services.settings.max_file_bytes)
        else:
            text, pages = body.text or "", [Page(text=body.text or "")]
        extracted, extraction_warnings = extract(services.provider, body.title, pages)
        model_meta = services.provider.health().get("models", [])
        model_digest = next((m.get("digest") for m in model_meta if isinstance(m, dict)
                             and m.get("name") in {services.settings.llm_model, services.settings.llm_model + ":latest"}), None)
        return {"modelDigest": model_digest, "text": text, "pages": [p.model_dump() for p in pages],
                "extraction": extracted.model_dump(mode="json"), "warnings": warnings + extraction_warnings,
                "model": services.settings.llm_model, "promptVersion": PROMPT_VERSION,
                "schemaVersion": SCHEMA_VERSION, "parserVersion": PARSER_VERSION}

    @app.post("/internal/index", dependencies=[Depends(authorize)])
    def index(body: IndexRequest):
        return services.archive.index_document(body.documentId, body.title, body.version, body.text, body.pages,
                                               [c.model_dump() for c in body.corrections])

    @app.post("/internal/remove", dependencies=[Depends(authorize)])
    def remove(body: RemoveRequest):
        return services.archive.remove(body.documentId)

    @app.post("/internal/ask", dependencies=[Depends(authorize)])
    def ask(body: AskRequest):
        return services.archive_rag.ask(body.question, body.documentIds)

    @app.post("/internal/consultation", dependencies=[Depends(authorize)])
    def prepare(body: ConsultationRequest):
        return consultation(services.provider, body.question, [c.text for c in body.contexts])

    return app


def create_mcp(services: Services | None = None) -> FastMCP:
    services = services or get_services()
    public = services.public_output
    mcp = FastMCP("Local Medical Archive — synthetic medical archive", mask_error_details=True,
        middleware=[PublicToolErrors()], instructions=
        "Search the SYNTHETIC medical archive for visits, laboratory results, prescriptions, timelines and "
        "verification facts. Answers and excerpts undergo a local privacy check. Source aliases are scoped "
        "to one response; they cannot resolve local files. This server has no access to the user's real "
        "medical archive and does not provide general medical advice. If the index is empty, index "
        "./sample_docs first. Use ask_question for grounded answers and find_relevant_docs for evidence.")

    @mcp.tool(description="Index synthetic medical visits, laboratory reports and prescriptions under the "
              "fixed allowed ./sample_docs folder. Supports Markdown, plain text and text PDF. "
              "Returns safe numerical statistics. Uses local embeddings, no generative model. "
              "Re-index after source changes; arbitrary folders and the private archive are inaccessible.")
    def index_folder(path: str = "./sample_docs", glob: str = "**/*") -> dict:
        return public.indexing(services.demo.index_folder(path, glob))

    @mcp.tool(description="Check numerical file/chunk statistics of the synthetic medical archive. "
              "No document content, paths or model calls. Empty means index_folder must be called before "
              "asking about synthetic visits, lab values or prescription details.")
    def index_status() -> dict:
        return public.status(services.demo.status())

    @mcp.tool(description="Find relevant medical source excerpts using BM25 plus vector search and RRF. "
              "A local privacy model checks and cleans ALL excerpts before returning them with per-response "
              "source aliases. No answer generation, query rewrite or relevance grading is performed. "
              "If privacy validation fails, no raw excerpts are returned.")
    def find_relevant_docs(query: str, top_k: int = 5) -> dict:
        if not query.strip() or len(query) > 4000:
            raise ServiceError("INVALID_QUESTION", "Недопустимый запрос.")
        sources = [source_of(d, demo=True) for d in services.demo.retrieve(query, top_k)]
        return public.checked(sources)

    @mcp.tool(description="Answer factual questions about synthetic medical visits, lab measurements, "
              "prescriptions, intervals and negations. Runs Corrective RAG: query rewrite, hybrid retrieval, "
              "per-chunk relevance grading, at most two corrective searches and a grounded answer or "
              "insufficient-data response. A local privacy check cleans BOTH answer and source excerpts. "
              "Returns only checked text and per-response source aliases. No raw identifying metadata, "
              "raw source filenames or traces. No raw fallback if checking fails.")
    def ask_question(question: str) -> dict:
        raw = services.demo_rag.ask(question)
        return public.checked(raw["sources"], answer=raw["answer"],
                              insufficient_context=raw["insufficientContext"], answer_parts=raw.get("answerParts"))

    return mcp