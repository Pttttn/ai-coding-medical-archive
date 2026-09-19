import re
from typing import Any, TypedDict

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaError
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph

from .config import Settings
from .errors import ServiceError
from .indexer import Corpus, source_of


class RagState(TypedDict, total=False):
    question: str
    query: str
    document_ids: list[str] | None
    retry_count: int
    chunks: list[Document]
    relevant: list[Document]
    trace: list[dict]
    result: dict


QUERY_SCHEMA = {"type": "object", "additionalProperties": False,
    "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 1200}}, "required": ["query"]}
GRADE_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"relevant": {"type": "boolean"},
    "evidence": {"type": "string", "maxLength": 900, "description": "One short exact excerpt; empty if unrelated"}},
    "required": ["relevant", "evidence"]}
ANSWER_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "evidence": {"type": "array", "maxItems": 12, "items": {"type": "object", "additionalProperties": False, "properties": {
        "citation": {"type": "integer", "minimum": 1},
        "quote": {"type": "string", "minLength": 1, "maxLength": 1600, "description": "Short verbatim excerpt, never a paraphrase or invented answer"}},
        "required": ["citation", "quote"]}},
    "insufficientContext": {"type": "boolean"}}, "required": ["evidence", "insufficientContext"]}



def verified_excerpt(proposed: str, source: str) -> str | None:
    """Return only exact source bytes, tolerating model whitespace and separate verbatim lines."""
    proposed = re.sub(r"(?<=\d)([.,])\s+(?=\d)", r"\1", proposed.strip())
    if not proposed:
        return None
    if proposed in source:
        return proposed
    pattern = r"\s+".join(re.escape(part) for part in proposed.split())
    match = re.search(pattern, source)
    if match:
        return match[0]
    lines = [line.strip() for line in proposed.splitlines() if line.strip()]
    if len(lines) > 1 and all(line in source for line in lines):
        substantive = [line for line in lines if not line.startswith("#")]
        if substantive:
            return "\n".join(substantive)
    return None


class CorrectiveRAG:
    def __init__(self, corpus: Corpus, provider: Any, settings: Settings):
        self.corpus, self.provider, self.settings = corpus, provider, settings
        graph = StateGraph(RagState)
        for name in ("rewrite_query", "retrieve", "grade_chunks", "broaden_query", "generate_answer"):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "rewrite_query")
        graph.add_edge("rewrite_query", "retrieve")
        graph.add_edge("retrieve", "grade_chunks")
        graph.add_conditional_edges("grade_chunks", self.route,
                                    {"generate_answer": "generate_answer", "broaden_query": "broaden_query"})
        graph.add_edge("broaden_query", "retrieve")
        graph.add_edge("generate_answer", END)
        self.graph = graph.compile()

    def model_json(self, task: str, payload: dict, schema: dict) -> dict:
        try:
            output = self.provider.json(task, payload, schema)
            # Test adapters and future providers must satisfy the same strict contract.
            Draft202012Validator(schema).validate(output)
            return output
        except JSONSchemaError:
            return {"_modelError": "MODEL_OUTPUT_INVALID"}
        except ServiceError as exc:
            if exc.code not in {"MODEL_OUTPUT_LIMIT", "MODEL_OUTPUT_INVALID"}:
                raise
            # Malformed/truncated generation is not evidence and is not a provider outage.
            return {"_modelError": exc.code}

    def rewrite_query(self, state: RagState) -> dict:
        response = self.model_json("TASK: rewrite_query. Rewrite the question for searching a synthetic/local "
            "medical archive. Keep entities, dates, numbers, doses and negations. Return {query:string}.",
            {"question": state["question"]}, QUERY_SCHEMA)
        rewrite = str(response.get("query", state["question"]))[:4000]
        # The exact original is retained so even a lossy model rewrite cannot erase constraints.
        query = state["question"] if rewrite == state["question"] else state["question"] + "\n" + rewrite
        return {"query": query, "retry_count": 0, "trace": [{"node": "rewrite_query", "query": query}]}

    def retrieve(self, state: RagState) -> dict:
        chunks = self.corpus.retrieve(state["query"], self.settings.retrieval_k, state.get("document_ids"))
        return {"chunks": chunks, "trace": state["trace"] + [{"node": "retrieve", "query": state["query"],
                 "pass": state["retry_count"] + 1, "chunkIds": [d.metadata["chunkId"] for d in chunks]}]}

    def grade_chunks(self, state: RagState) -> dict:
        relevant, grades = [], []
        for document in state["chunks"]:
            output = self.model_json("TASK: grade_chunks. You are a SEARCH RELEVANCE classifier, not answering the question. "
                "Decide whether this source helps a reader answer it. relevant=true is NOT a yes answer: "
                "evidence establishing a NO answer is equally relevant. Do not judge whether the proposition "
                "in the question is true. When a specific named record/date is requested, a similar "
                "observation from a different record/date is not relevant. Return relevant true only with a verbatim evidence "
                "excerpt that helps answer at least one part. Negative findings and explicit unknown intake "
                "are evidence when they concern the requested subject. Generic disclaimers saying unstated "
                "information is unknown do NOT answer an unrelated question. If the requested subject is "
                "absent, return relevant false and evidence empty. Use ONE short evidence sentence at most. Never use outside knowledge.",
                {"question": state["question"], "chunk": document.page_content}, GRADE_SCHEMA)
            evidence = output.get("evidence", "")
            accepted = output.get("relevant") is True and isinstance(evidence, str) and \
                bool(evidence.strip()) and verified_excerpt(evidence, document.page_content) is not None
            if accepted:
                relevant.append(document)
            grades.append({"chunkId": document.metadata["chunkId"], "relevant": accepted,
                           "evidence": evidence if accepted else "", "errorCode": output.get("_modelError")})
        return {"relevant": relevant, "trace": state["trace"] + [{"node": "grade_chunks", "grades": grades}]}

    def route(self, state: RagState) -> str:
        return "generate_answer" if len(state["relevant"]) >= self.settings.min_relevant_chunks or \
            state["retry_count"] >= self.settings.rag_max_corrective_retries else "broaden_query"

    def broaden_query(self, state: RagState) -> dict:
        output = self.model_json("TASK: broaden_query. Broaden the archive search with related terms or "
            "synonyms, keeping the original entities, numerical constraints and negations. Do not answer "
            "the question. Return {query:string}.", {"question": state["question"],
            "previousQuery": state["query"], "retry": state["retry_count"] + 1}, QUERY_SCHEMA)
        query = state["question"] + "\n" + str(output.get("query", state["question"]))[:4000]
        return {"query": query, "retry_count": state["retry_count"] + 1,
                "trace": state["trace"] + [{"node": "broaden_query", "query": query}]}

    def generate_answer(self, state: RagState) -> dict:
        chunks = state["relevant"]
        trace = state["trace"] + [{"node": "generate_answer"}]

        def abstain():
            return {"result": {"answer": "В архиве недостаточно подтверждённых данных для ответа на этот вопрос.",
                    "sources": [], "insufficientContext": True, "trace": trace,
                    "retryCount": state["retry_count"]}}

        if len(chunks) < self.settings.min_relevant_chunks:
            return abstain()
        # Small local models can invert negations even with valid citation IDs. Therefore this
        # generation selects exact supporting quotations; the server assembles the final answer.
        # No unchecked free-form model claim is exposed as a medical archive fact.
        quotes = []
        for attempt in range(2):
            output = self.model_json("TASK: generate_answer. Select VERBATIM source sentences that answer "
                "the question. Return evidence entries containing the 1-based citation and the EXACT quote "
                "copied from that source. Cover all requested parts when available. Preserve negation, "
                "uncertainty, dose, units, dates and full decimal numbers. A prescription never proves intake. "
                "For a named record or date, use evidence about that record/date, never a similar observation "
                "from a different record. For a correction include both original and corrected evidence. Do not compose a new sentence "
                "or supply general knowledge. If sources do not discuss the requested subject, return no "
                "evidence and insufficientContext true. Ignore unrelated generic disclaimers. "
                "Each quote must occur EXACTLY in its cited source. An earlier invalid result, if any, must "
                "be corrected by copying source text, never by inventing it. Select at most one short sentence per requested fact.",
                {"question": state["question"], "validationAttempt": attempt,
                 "sources": [{"number": i + 1, "text": d.page_content,
                              "userCorrection": d.metadata.get("userCorrection", False)}
                             for i, d in enumerate(chunks)]}, ANSWER_SCHEMA)
            if output.get("_modelError"):
                trace.append({"node": "generation_validation", "errorCode": output["_modelError"]})
                continue
            if output.get("insufficientContext") is True:
                return abstain()
            entries = output.get("evidence", [])
            if not isinstance(entries, list) or not entries:
                continue
            valid = []
            for entry in entries:
                number, quote = entry.get("citation"), entry.get("quote")
                if type(number) is not int or not 1 <= number <= len(chunks) or \
                        not isinstance(quote, str) or not quote.strip() or \
                        verified_excerpt(quote, chunks[number - 1].page_content) is None:
                    valid = []
                    break
                valid.append((number, verified_excerpt(quote, chunks[number - 1].page_content)))
            if valid:
                quotes = list(dict.fromkeys(valid))
                break
        if not quotes:
            return abstain()
        used = list(dict.fromkeys(number for number, _ in quotes))
        sources = [{"citation": i, **source_of(chunks[i - 1], demo=self.corpus.name == "mcp_demo")} for i in used]
        introduction = "По источникам архива:" if re.search(r"[А-Яа-яЁё]", state["question"]) else "Archive evidence:"
        answer = introduction + "\n\n" + "\n\n".join(f"{quote} [{number}]" for number, quote in quotes)
        result = {"answer": answer, "sources": sources, "insufficientContext": False,
                  "trace": trace, "retryCount": state["retry_count"]}
        if self.corpus.name == "mcp_demo":
            # Keep citation structure separate from verbatim medical text for the public boundary.
            result["answerParts"] = [{"citation": number, "text": quote} for number, quote in quotes]
        return {"result": result}

    def ask(self, question: str, document_ids: list[str] | None = None) -> dict:
        if not question.strip() or len(question) > 4000:
            raise ServiceError("INVALID_QUESTION", "Вопрос должен содержать от 1 до 4000 символов.")
        result = self.graph.invoke({"question": question, "document_ids": document_ids},
                                   config={"recursion_limit": 20})["result"]
        # Content-bearing debug traces are only exposed for explicitly synthetic MCP/evaluation.
        if self.corpus.name != "mcp_demo":
            result.pop("trace", None)
        return result
