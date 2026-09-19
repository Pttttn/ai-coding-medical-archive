from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(StrictModel):
    pageNumber: int | None = Field(default=None, ge=1)
    text: str


class Provenance(StrictModel):
    page: int | None = Field(default=None, ge=1)
    sourceText: str = Field(min_length=1)


class Fact(StrictModel):
    type: Literal["CONDITION", "SYMPTOM", "MEDICATION", "LAB_RESULT", "PROCEDURE",
                  "RECOMMENDATION", "OBSERVATION", "OTHER"]
    name: str = Field(min_length=1, max_length=500)
    valueText: str | None = None
    valueNumber: float | None = None
    unit: str | None = None
    eventDate: date | None = None
    assertionStatus: Literal["CONFIRMED", "SUSPECTED", "NEGATED", "PRESCRIBED", "UNKNOWN"] = "UNKNOWN"
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: Provenance


class Extraction(StrictModel):
    documentType: Literal["LAB_REPORT", "VISIT", "VISIT_TRANSCRIPT", "DISCHARGE_SUMMARY", "PRESCRIPTION",
                          "IMAGING_REPORT", "PROCEDURE_REPORT", "NOTE", "OTHER"]
    documentDate: date | None = None
    summary: str
    tags: list[str] = Field(default_factory=list, max_length=30)
    facts: list[Fact] = Field(default_factory=list, max_length=200)


class ProcessRequest(StrictModel):
    documentId: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    title: str = Field(max_length=500)
    text: str | None = Field(default=None, max_length=2000000)
    filePath: str | None = None


class Correction(StrictModel):
    id: str
    name: str
    valueText: str | None = None
    valueNumber: float | None = None
    unit: str | None = None
    reviewStatus: str


class IndexRequest(StrictModel):
    documentId: str = Field(min_length=1, max_length=200)
    title: str = Field(max_length=500)
    version: int = Field(ge=1)
    text: str = Field(max_length=2000000)
    pages: list[Page] | None = None
    corrections: list[Correction] = Field(default_factory=list)


class RemoveRequest(StrictModel):
    documentId: str


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    documentIds: list[str] | None = Field(default=None, max_length=100)


class Context(StrictModel):
    text: str = Field(max_length=50000)


class ConsultationRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    contexts: list[Context] = Field(max_length=30)
