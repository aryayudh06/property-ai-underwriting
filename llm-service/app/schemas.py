from typing import Optional, Any, List, Dict

from pydantic import BaseModel, Field, field_validator

from app.field_definitions import FIELD_DEFINITIONS


# ---------------- Request ----------------

class DocumentPageInput(BaseModel):
    page_number: int
    text: str = ""


class DocumentInput(BaseModel):
    document_id: str
    filename: str
    doc_type: str = "Unknown"
    pages: List[DocumentPageInput] = []


class ExtractRequest(BaseModel):
    case_id: str
    case_context: Optional[Dict[str, Any]] = None
    documents: List[DocumentInput] = Field(default_factory=list)


# ---------------- Validated Output ----------------

class FieldValue(BaseModel):
    value: Optional[Any] = None
    source_document: Optional[str] = None
    page: Optional[int] = None
    evidence: Optional[str] = None
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, v))

    @field_validator("page", mode="before")
    @classmethod
    def coerce_page(cls, v):
        if v in (None, "", "null"):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


class ExtractionResult(BaseModel):
    insured: Dict[str, FieldValue] = {}
    risk_location: Dict[str, FieldValue] = {}
    occupancy: Dict[str, FieldValue] = {}
    building: Dict[str, FieldValue] = {}
    assets: Dict[str, FieldValue] = {}
    fire_protection: Dict[str, FieldValue] = {}
    electrical_and_maintenance: Dict[str, FieldValue] = {}
    operations: Dict[str, FieldValue] = {}
    natural_perils: Dict[str, FieldValue] = {}
    loss_history: Dict[str, FieldValue] = {}
    coverage: Dict[str, FieldValue] = {}
    survey: Dict[str, FieldValue] = {}
    data_gaps: List[str] = []
    conflicts: List[str] = []
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_overall_confidence(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, v))


assert set(ExtractionResult.model_fields.keys()) >= set(FIELD_DEFINITIONS.keys()), (
    "ExtractionResult harus memiliki field untuk setiap kategori di FIELD_DEFINITIONS"
)


class ExtractResponse(BaseModel):
    result: ExtractionResult
    method: str  # "ollama" | "mock" | "mock_fallback"
    model: str
    warnings: List[str] = []


# ---------------- RAG: retrieval → context injection → Gemini ----------------
# Retrieval (embedding lokal + vector search) sepenuhnya dilakukan di Main API
# (backend/app/services/kb_service.py) karena di situlah database Knowledge
# Base (SQLite) berada. Service ini HANYA menerima potongan konteks yang sudah
# di-retrieve (sudah relevan) lalu meminta LLM (Gemini/Ollama/mock) menyusun
# jawaban/narasi yang digrounding ketat pada konteks tersebut.

class RagContextChunk(BaseModel):
    document_title: str
    document_category: str
    text: str
    relevance_score: float = 0.0


class RagAnswerRequest(BaseModel):
    query: str
    context_chunks: List[RagContextChunk] = Field(default_factory=list)
    case_context: Optional[Dict[str, Any]] = None
    # "qa": jawab pertanyaan bebas dari underwriter.
    # "narrative": susun narasi/ringkasan atas daftar kondisi rule-engine yang diberikan di query.
    mode: str = "qa"


class RagAnswerResponse(BaseModel):
    answer: str
    method: str  # "gemini" | "ollama" | "mock" | "mock_fallback"
    model: str
    grounded: bool  # True jika context_chunks tidak kosong (ada dasar rujukan)
    warnings: List[str] = []
