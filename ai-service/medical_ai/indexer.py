import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from rank_bm25 import BM25Okapi

from .chunking import SPLITTER_VERSION, MedicalTextSplitter
from .config import Settings
from .errors import ServiceError
from .parsing import SUPPORTED_EXTENSIONS, confined_path, parse_file
from .recipe import index_settings
from .schemas import Page


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.casefold()) or ["_"]


class RankedRetriever(BaseRetriever):
    """Adapter for already-ranked BM25/Chroma results; EnsembleRetriever performs RRF."""
    documents: list[Document]

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        return self.documents


class Corpus:
    def __init__(self, name: str, settings: Settings, provider: Any):
        if name not in {"archive", "mcp_demo"}:
            raise ValueError("Unknown corpus")
        self.name, self.settings, self.provider = name, settings, provider
        folder = settings.mcp_demo_dir if name == "mcp_demo" and settings.mcp_demo_dir else settings.data_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(folder / "metadata.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, hash TEXT, source TEXT, indexed_at TEXT);
            CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, document_id TEXT, text TEXT,
                                             metadata TEXT, embedding TEXT);
            CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(document_id);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS revisions(document_id TEXT, revision_id TEXT, hash TEXT, indexed_at TEXT,
                                                 PRIMARY KEY(document_id, revision_id));
        """)
        self.client = chromadb.PersistentClient(path=str(folder / "chroma"),
                                               settings=ChromaSettings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection("chunks", embedding_function=None,
                                                               metadata={"hnsw:space": "cosine"})
        configured = self.db.execute("SELECT value FROM settings WHERE key='embedding_model'").fetchone()
        if configured and configured[0] != settings.embedding_model and self.collection.count():
            raise ServiceError("EMBEDDING_MODEL_CHANGED", "Для смены embedding-модели нужен новый DATA_DIR.", 503)
        self.db.execute("INSERT OR REPLACE INTO settings VALUES('embedding_model', ?)", (settings.embedding_model,))
        self.db.commit()
        self._restore()

    def _restore(self):
        """SQLite is authoritative; repair interrupted vector mutations using stored embeddings."""
        with self.lock:
            rows = self.db.execute("SELECT * FROM chunks ORDER BY document_id,id").fetchall()
            current = set(self.collection.get(include=[])["ids"])
            wanted = {r["id"] for r in rows}
            if current - wanted:
                self.collection.delete(ids=list(current - wanted))
            # Content-addressed IDs change whenever source/configuration changes.
            # Existing IDs already contain the committed vectors; re-upserting them
            # on every restart can change the HNSW graph without changing the data.
            missing = [row for row in rows if row["id"] not in current]
            for start in range(0, len(missing), 100):
                batch = missing[start:start + 100]
                if batch:
                    self.collection.upsert(ids=[r["id"] for r in batch],
                                           documents=[r["text"] for r in batch],
                                           metadatas=[json.loads(r["metadata"]) for r in batch],
                                           embeddings=[json.loads(r["embedding"]) for r in batch])
            self._refresh_sparse()

    def _refresh_sparse(self):
        self.rows = [dict(r) for r in self.db.execute("SELECT * FROM chunks ORDER BY document_id,id")]
        self.documents = [Document(page_content=r["text"], metadata=json.loads(r["metadata"])) for r in self.rows]
        self.bm25 = BM25Okapi([tokenize(d.page_content) for d in self.documents]) if self.documents else None

    def status(self) -> dict:
        with self.lock:
            count, last = self.db.execute("SELECT COUNT(*),MAX(indexed_at) FROM documents").fetchone()
            return {"files": count, "chunks": len(self.rows), "lastIndexedAt": last,
                    "corpus": self.name, "embeddingModel": self.settings.embedding_model,
                    "chunkSize": self.settings.chunk_size, "chunkOverlap": self.settings.chunk_overlap}

    def _revision_chunk_ids(self, document_id: str, revision_id: str | None) -> list[str]:
        if revision_id is None:
            return [r[0] for r in self.db.execute("SELECT id FROM chunks WHERE document_id=?", (document_id,))]
        return [r[0] for r in self.db.execute(
            "SELECT id FROM chunks WHERE document_id=? AND json_extract(metadata,'$.revisionId')=?", (document_id, revision_id))]

    def index_document(self, document_id: str, title: str, version: int, text: str,
                       pages: list[Page] | None = None, corrections: list[dict] | None = None,
                       revision_id: str | None = None, expected_settings: dict | None = None) -> dict:
        """Without revision_id the document's chunks are replaced (legacy). With it, only that
        processing revision is (re)staged: the active revision stays searchable until activation."""
        # A staged revision reports the index settings actually used, so the backend can compare them with
        # the extraction recipe; a changed embedding digest also changes the hash and forces re-embedding.
        used = None
        if revision_id is not None:
            health = self.provider.health()
            used = index_settings(self.settings, health.get("models", []))
            if used["embeddingDigest"] is None and health.get("ollama") is False:
                raise ServiceError("EMBEDDING_UNAVAILABLE", "Локальная embedding-модель недоступна.", 503)
            # Refuse before writing: chunks of a revision are built only with the settings its recipe names.
            if expected_settings is not None and expected_settings != used:
                raise ServiceError("INDEX_RECIPE_MISMATCH", "Настройки индекса не совпадают с рецептом обработки.", 409)
        content_hash = hashlib.sha256(json.dumps([title, version, text,
            [p.model_dump() for p in pages] if pages else None, corrections,
            self.settings.embedding_model, self.settings.chunk_size, self.settings.chunk_overlap, SPLITTER_VERSION]
            + ([revision_id, used] if revision_id is not None else []),
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        manifest = {"revisionId": revision_id, "contentHash": content_hash, "indexSettings": used}
        with self.lock:
            existing = (self.db.execute("SELECT hash FROM documents WHERE id=?", (document_id,)).fetchone()
                        if revision_id is None else
                        self.db.execute("SELECT hash FROM revisions WHERE document_id=? AND revision_id=?",
                                        (document_id, revision_id)).fetchone())
            if existing and existing[0] == content_hash:
                return {"ok": True, "unchanged": True, **manifest,
                        "documentChunks": len(self._revision_chunk_ids(document_id, revision_id)), **self.status()}
            splitter = MedicalTextSplitter(chunk_size=self.settings.chunk_size,
                                           chunk_overlap=self.settings.chunk_overlap)
            chunks = []
            for page in pages or [Page(text=text)]:
                for chunk in splitter.split_text(page.text):
                    chunks.append((chunk, page.pageNumber or 0, False))
            for correction in corrections or []:
                if correction.get("reviewStatus") not in {"CONFIRMED", "CORRECTED"}:
                    continue
                value = "; ".join(str(v) for v in [correction.get("valueText"), correction.get("valueNumber")]
                                  if v is not None)
                marker = "[Пользовательское исправление; не цитата оригинала] "
                correction_text = (f"{correction['name']}: {value} {correction.get('unit') or ''} "
                                   f"(correctionId={correction['id']})")
                correction_splitter = MedicalTextSplitter(self.settings.chunk_size - len(marker))
                chunks.extend((marker + part, 0, True) for part in correction_splitter.split_text(correction_text))
            embeddings = self.provider.embed([c[0] for c in chunks]) if chunks else []
            new_rows = []
            for position, ((chunk, page, corrected), embedding) in enumerate(zip(chunks, embeddings), 1):
                chunk_id = hashlib.sha256(f"{document_id}:{content_hash}:{position}".encode()).hexdigest()
                metadata = {"chunkId": chunk_id, "documentId": document_id, "source": title,
                            "version": version, "position": position, "pageNumber": page,
                            "userCorrection": corrected}
                if revision_id is not None:
                    metadata["revisionId"] = revision_id
                new_rows.append((chunk_id, document_id, chunk, json.dumps(metadata, ensure_ascii=False),
                                 json.dumps(embedding)))
            old_ids = self._revision_chunk_ids(document_id, revision_id)
            now = datetime.now(timezone.utc).isoformat()
            try:
                self.db.execute("BEGIN")
                self.db.executemany("DELETE FROM chunks WHERE id=?", [(i,) for i in old_ids])
                self.db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", new_rows)
                if revision_id is None:
                    self.db.execute("DELETE FROM revisions WHERE document_id=?", (document_id,))
                    self.db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?)", (document_id, content_hash, title, now))
                else:
                    # Legacy hash no longer describes the document's chunks; keep the row for file counts.
                    self.db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?)", (document_id, None, title, now))
                    self.db.execute("INSERT OR REPLACE INTO revisions VALUES(?,?,?,?)", (document_id, revision_id, content_hash, now))
                if old_ids:
                    self.collection.delete(ids=old_ids)
                for start in range(0, len(new_rows), 100):
                    batch = new_rows[start:start + 100]
                    self.collection.upsert(ids=[r[0] for r in batch], documents=[r[2] for r in batch],
                                           metadatas=[json.loads(r[3]) for r in batch],
                                           embeddings=[json.loads(r[4]) for r in batch])
                self.db.commit()
            except Exception:
                self.db.rollback()
                self._restore()
                raise
            self._refresh_sparse()
            return {"ok": True, "unchanged": False, **manifest, "documentChunks": len(new_rows), **self.status()}

    def prune(self, document_id: str, keep_revision_id: str) -> dict:
        """After activation: drop every other staged, superseded or legacy chunk set of the document."""
        with self.lock:
            ids = [r[0] for r in self.db.execute(
                "SELECT id FROM chunks WHERE document_id=? AND json_extract(metadata,'$.revisionId') IS NOT ?",
                (document_id, keep_revision_id))]
            self.db.executemany("DELETE FROM chunks WHERE id=?", [(i,) for i in ids])
            self.db.execute("DELETE FROM revisions WHERE document_id=? AND revision_id<>?", (document_id, keep_revision_id))
            self.db.commit()
            self._refresh_sparse()
            if ids:
                self.collection.delete(ids=ids)
        return {"ok": True, "removedChunks": len(ids)}

    def visible(self, document_ids: list[str] | None = None, revisions: dict[str, str | None] | None = None) -> list[Document]:
        """Chunks readable in one snapshot: with `revisions`, only each document's active revision
        (None = legacy chunks without a revision). Staged or superseded revisions are never visible."""
        allowed = set(document_ids) if document_ids is not None else None
        return [d for d in self.documents if (allowed is None or d.metadata["documentId"] in allowed)
                and (revisions is None or d.metadata.get("revisionId") == revisions.get(d.metadata["documentId"]))]

    def remove(self, document_id: str):
        with self.lock:
            ids = [r[0] for r in self.db.execute("SELECT id FROM chunks WHERE document_id=?", (document_id,))]
            self.db.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
            self.db.execute("DELETE FROM documents WHERE id=?", (document_id,))
            self.db.execute("DELETE FROM revisions WHERE document_id=?", (document_id,))
            self.db.commit()
            self._refresh_sparse()
            if ids:
                self.collection.delete(ids=ids)
        return {"ok": True}

    def retrieve(self, query: str, top_k: int = 5, document_ids: list[str] | None = None, *, archive_scan: bool = False,
                 revisions: dict[str, str | None] | None = None) -> list[Document]:
        maximum = 1000 if archive_scan and self.name == "archive" else 20
        if not 1 <= top_k <= maximum:
            raise ServiceError("INVALID_TOP_K", "top_k должен быть от 1 до 20.")
        with self.lock:
            if not self.documents or document_ids == []:
                return []
            allowed = set(document_ids) if document_ids is not None else None
            eligible = self.visible(document_ids, revisions)
            if not eligible:
                return []
            depth = min(max(top_k * 2, self.settings.retrieval_k), len(eligible))
            # Recompute BM25 over the selected corpus so excluded documents cannot affect IDF.
            sparse_model = self.bm25 if allowed is None and revisions is None else BM25Okapi([tokenize(d.page_content) for d in eligible])
            scores = sparse_model.get_scores(tokenize(query))
            sparse = [eligible[i] for i in sorted(range(len(eligible)), key=lambda i: (-scores[i], eligible[i].metadata["chunkId"]))[:depth]]
            where = {"documentId": {"$in": sorted(allowed)}} if allowed else None
            vector_results = self.collection.query(query_embeddings=self.provider.embed([query]),
                n_results=len(eligible), where=where, include=["distances"])
            active = {d.metadata["chunkId"]: d for d in eligible}
            # The MVP corpus is small: rank every eligible vector before truncation.
            # Sorting only an ANN top-k cannot resolve tied candidates already dropped
            # at the cutoff. Fetch IDs/distances, not a second copy of all source text.
            candidates = [(distance, identifier) for identifier, distance in
                          zip(vector_results["ids"][0], vector_results["distances"][0]) if identifier in active]
            candidates.sort(key=lambda item: (item[0], item[1]))
            dense = [active[identifier] for _, identifier in candidates[:depth]]
            combined = EnsembleRetriever(retrievers=[RankedRetriever(documents=sparse), RankedRetriever(documents=dense)],
                                         weights=[0.5, 0.5], c=60, id_key="chunkId")
            return combined.invoke(query)[:top_k]

    def index_folder(self, path: str = "./sample_docs", glob: str = "**/*") -> dict:
        if self.name != "mcp_demo":
            raise ServiceError("CORPUS_NOT_ALLOWED", "Операция доступна только синтетическому корпусу.", 403)
        if not glob or Path(glob).is_absolute() or ".." in Path(glob).parts or "\\" in glob or ":" in glob:
            raise ServiceError("PATH_NOT_ALLOWED", "Недопустимый glob-паттерн.", 403)
        root = self.settings.sample_docs_dir.resolve()
        supplied = Path(path)
        if path.replace("\\", "/").rstrip("/") in {"sample_docs", "./sample_docs"}:
            folder = root
        elif not supplied.is_absolute() and supplied.parts and supplied.parts[0] == "sample_docs":
            folder = confined_path(root.joinpath(*supplied.parts[1:]), root)
        else:
            folder = confined_path(supplied, root)
        if not folder.is_dir():
            raise ServiceError("FOLDER_NOT_FOUND", "Разрешённый каталог не найден.", 404)
        indexed, unchanged, skipped, errors = 0, 0, [], []
        for candidate in sorted(folder.glob(glob)):
            relative = candidate.relative_to(root).as_posix()
            try:
                safe = confined_path(candidate, root)
                if not safe.is_file():
                    continue
                if (candidate.suffix.lower() not in SUPPORTED_EXTENSIONS
                        or safe.suffix.lower() not in SUPPORTED_EXTENSIONS):
                    skipped.append({"source": relative, "reason": "UNSUPPORTED_FORMAT"})
                    continue
                text, pages, warnings = parse_file(safe, self.settings.max_file_bytes)
                result = self.index_document("demo:" + relative, relative, 1, text, pages)
                unchanged += int(result["unchanged"])
                indexed += int(not result["unchanged"])
                if warnings:
                    skipped.append({"source": relative, "warnings": warnings})
            except ServiceError as exc:
                errors.append({"source": relative, "code": exc.code, "message": exc.message})
        removed = 0
        with self.lock:
            docs = self.db.execute("SELECT id,source FROM documents").fetchall()
            for doc in docs:
                candidate = root / doc["source"]
                try:
                    safe = confined_path(candidate, root)
                    retained = (safe.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS
                                and safe.suffix.lower() in SUPPORTED_EXTENSIONS)
                except ServiceError:
                    retained = False
                # Reconcile the entire persisted corpus even for a narrow glob:
                # deleted, escaped and now-unsupported files must not stay queryable.
                if not retained:
                    self.remove(doc["id"])
                    removed += 1
        return {"indexed": indexed, "unchanged": unchanged, "removed": removed,
                "skipped": skipped, "errors": errors, **self.status()}


def source_of(document: Document, *, demo: bool = False) -> dict:
    metadata = document.metadata
    source = {"source": metadata["source"], "chunkId": metadata["chunkId"],
              "position": metadata["position"], "pageNumber": metadata.get("pageNumber") or None,
              "text": document.page_content, "version": metadata["version"],
              "userCorrection": metadata.get("userCorrection", False)}
    if not demo:
        source["documentId"] = metadata["documentId"]
    return source

