import ipaddress
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
    ollama_base_url: str = Field(default="http://ollama:11434", validation_alias=AliasChoices("OLLAMA_BASE_URL", "LLM_BASE_URL"))
    llm_model: str = "qwen3.5:2b"
    embedding_model: str = "nomic-embed-text"
    internal_token: str = Field(default="local-development-token-change-me", validation_alias=AliasChoices("INTERNAL_TOKEN", "INTERNAL_API_TOKEN"))
    data_dir: Path = Field(default=Path("./data"), validation_alias=AliasChoices("DATA_DIR", "AI_DATA_DIR"))
    mcp_demo_dir: Path | None = None
    sample_docs_dir: Path = Path("../sample_docs")
    upload_dir: Path = Path("/data/uploads")
    chunk_size: int = Field(default=900, ge=200, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    retrieval_k: int = Field(default=5, ge=1, le=12)
    min_relevant_chunks: int = Field(default=1, ge=1, le=12)
    rag_max_corrective_retries: int = Field(default=2, ge=0, le=2)
    llm_seed: int = Field(default=42, ge=0, le=2147483647)
    llm_timeout: float = 180.0
    llm_query_max_tokens: int = Field(default=128, ge=32, le=512)
    llm_grade_max_tokens: int = Field(default=256, ge=64, le=768)
    llm_answer_max_tokens: int = Field(default=1024, ge=128, le=2048)
    llm_extraction_max_tokens: int = Field(default=2048, ge=256, le=4096)
    llm_privacy_max_tokens: int = Field(default=1024, ge=128, le=2048)
    archive_scan_chunks: int = Field(default=120, ge=12, le=500)
    archive_batch_chunks: int = Field(default=6, ge=1, le=8)
    archive_evidence_max_tokens: int = Field(default=4096, ge=512, le=8192)
    extraction_max_facts_per_batch: int = Field(default=8, ge=2, le=32)
    extraction_profile: Literal['legacy', 'lab-rows-v1', 'clinical-v1'] = 'legacy'
    max_file_bytes: int = 20 * 1024 * 1024
    internal_port: int = 8001
    mcp_port: int = 8002
    bind_host: str = "0.0.0.0"

    @model_validator(mode="after")
    def overlap_is_smaller(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        endpoint = urlparse(self.ollama_base_url)
        allowed = {"localhost", "ollama", "host-ollama", "host.docker.internal"}
        if endpoint.hostname not in allowed:
            try:
                local = ipaddress.ip_address(endpoint.hostname or "").is_private
            except ValueError:
                local = False
            if not local:
                raise ValueError("Only local Ollama endpoints are permitted")
        if endpoint.scheme not in {"http", "https"} or endpoint.username or endpoint.password:
            raise ValueError("Invalid local Ollama endpoint")
        archive = (self.data_dir / "archive").resolve()
        demo = (self.mcp_demo_dir or self.data_dir / "mcp_demo").resolve()
        if demo == archive or archive.is_relative_to(demo) or demo.is_relative_to(archive):
            raise ValueError("MCP demo storage must not overlap archive storage")
        return self



