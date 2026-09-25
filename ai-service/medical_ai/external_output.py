"""The single public MCP output boundary; raw archive/RAG contracts remain internal."""
import json
import secrets
from datetime import datetime, timezone

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from .errors import ServiceError
from .privacy import sanitize_fields

PUBLIC_ERROR = "PUBLIC_OUTPUT_UNAVAILABLE: unable to return a checked response."
PUBLIC_WARNINGS = ["AUTOMATED_CHECK_NOT_ANONYMITY_GUARANTEE"]


class PublicToolErrors(Middleware):
    """Also catches framework argument/unknown-tool failures before they echo client data."""
    async def on_call_tool(self, context, call_next):
        try:
            allowed = {"index_folder": {"path", "glob"}, "index_status": set(),
                       "find_relevant_docs": {"query", "top_k"}, "ask_question": {"question"}}
            name, arguments = context.message.name, context.message.arguments or {}
            if name not in allowed or not set(arguments) <= allowed[name]:
                raise ValueError("Invalid public tool request")
            return await call_next(context)
        except Exception:
            # Never echo error messages, invalid inputs, paths, model output or validation details.
            raise ToolError(PUBLIC_ERROR) from None


class PublicOutput:
    def __init__(self, corpus, provider):
        if corpus.name != "mcp_demo":
            raise ValueError("Public output requires the fixed demo corpus")
        self.corpus, self.provider = corpus, provider
        with corpus.lock:
            corpus.db.execute("""CREATE TABLE IF NOT EXISTS public_references(
                response_ref TEXT NOT NULL, reference TEXT NOT NULL, metadata TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(response_ref,reference))""")
            corpus.db.commit()

    def status(self, raw: dict) -> dict:
        return {"status": "READY" if raw["files"] else "EMPTY", "corpus": "mcp_demo",
                **{name: int(raw[name]) for name in ("files", "chunks", "chunkSize", "chunkOverlap")}}

    def indexing(self, raw: dict) -> dict:
        return {**self.status(raw), **{name: int(raw[name]) for name in ("indexed", "unchanged", "removed")},
                "skipped": len(raw["skipped"]), "errors": len(raw["errors"])}

    def _remember(self, response_ref: str, sources: list[dict]):
        # The mapping is local, in mcp_demo/metadata.sqlite3, never available as an MCP tool.
        rows = []
        for i, source in enumerate(sources, 1):
            metadata = {key: source[key] for key in ("source", "chunkId", "position", "pageNumber",
                        "version", "userCorrection", "citation") if key in source}
            rows.append((response_ref, f"S{i}", json.dumps(metadata, ensure_ascii=False),
                         datetime.now(timezone.utc).isoformat()))
        with self.corpus.lock:
            self.corpus.db.executemany("INSERT INTO public_references VALUES(?,?,?,?)", rows)
            self.corpus.db.commit()

    def resolve_local(self, response_ref: str) -> dict[str, dict]:
        """Local evaluator/debugging only. Deliberately absent from the public tool registry."""
        with self.corpus.lock:
            rows = self.corpus.db.execute("SELECT reference,metadata FROM public_references WHERE response_ref=?",
                                          (response_ref,)).fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    def checked(self, sources: list[dict], *, answer: str | None = None,
                insufficient_context: bool = False, answer_parts: list[dict] | None = None) -> dict:
        if not isinstance(sources, list) or len(sources) > 20 or any(
                not isinstance(s, dict) or not isinstance(s.get("text"), str) for s in sources):
            raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
        context = "\n".join(source["text"] for source in sources)
        fields = [source["text"] for source in sources]
        prefix_count, parts, aliases = 0, [], {}
        if answer is not None:
            if not isinstance(answer, str):
                raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
            if insufficient_context:
                if sources or answer_parts:
                    raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
                fields = ["В архиве недостаточно подтверждённых данных для ответа на этот вопрос."]
                prefix_count = 1
            else:
                from .rag import verified_excerpt
                if not isinstance(answer_parts, list) or not 1 <= len(answer_parts) <= 12:
                    raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
                numbered = {}
                for i, source in enumerate(sources, 1):
                    citation = source.get("citation")
                    if type(citation) is not int or citation < 1 or citation in numbered:
                        raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
                    numbered[citation], aliases[citation] = source, f"S{i}"
                for part in answer_parts:
                    if (not isinstance(part, dict) or set(part) != {"citation", "text"}
                            or type(part["citation"]) is not int or part["citation"] not in numbered
                            or not isinstance(part["text"], str)
                            # Only one contiguous source span is an answer part, never glued lines.
                            or verified_excerpt(part["text"], numbered[part["citation"]]["text"])
                            != part["text"].strip()):
                        raise ServiceError("PRIVACY_CHECK_FAILED", "Проверка приватности не завершена.", 502)
                    parts.append(part)
                fields = [part["text"] for part in parts] + fields
                prefix_count = len(parts)
        checked = sanitize_fields(self.provider, fields, identifier_context=context, strict=True)
        response_ref = "R" + secrets.token_hex(16)
        cleaned = checked["texts"][prefix_count:]
        public_sources = [{"reference": f"S{i}", "text": text} for i, text in enumerate(cleaned, 1)]
        privacy = {"status": "checked", "warnings": PUBLIC_WARNINGS +
                   (["QUASI_IDENTIFIERS_REQUIRE_CAUTION"] if checked["warnings"] else [])}
        result = {"responseRef": response_ref, "privacy": privacy}
        if answer is None:
            result["chunks"] = public_sources
        else:
            if insufficient_context:
                safe_answer = checked["texts"][0]
            else:
                intro = "По источникам архива:" if answer.startswith("По источникам архива:") else "Archive evidence:"
                safe_answer = intro + "\n\n" + "\n\n".join(
                    f"{text} [{aliases[part['citation']]}]" for text, part in zip(checked["texts"], parts))
            result.update(answer=safe_answer, sources=public_sources,
                          insufficientContext=bool(insufficient_context))
        self._remember(response_ref, sources)
        return result