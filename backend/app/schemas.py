from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.models import CaseStatus, DocumentType, ProcessingStatus


# ---------- Case ----------

class CaseBase(BaseModel):
    quotation_policy_no: str = Field(..., min_length=1, max_length=100)
    insured_name: str = Field(..., min_length=1, max_length=200)
    risk_location: str = Field(..., min_length=1, max_length=300)
    occupation_business: str = Field(..., min_length=1, max_length=200)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    branch: Optional[str] = None


class CaseCreate(CaseBase):
    status: Optional[CaseStatus] = CaseStatus.DRAFT


class CaseUpdate(BaseModel):
    quotation_policy_no: Optional[str] = None
    insured_name: Optional[str] = None
    risk_location: Optional[str] = None
    occupation_business: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    branch: Optional[str] = None
    status: Optional[CaseStatus] = None


class CaseStatusUpdate(BaseModel):
    status: CaseStatus


class CaseOut(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class CaseDetailOut(CaseOut):
    documents: List["DocumentOut"] = []


# ---------- Case History ----------

class CaseHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    action: str
    description: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime


# ---------- Document ----------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    original_filename: str
    doc_type: DocumentType
    file_format: str
    file_size: int
    page_count: int
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    page_number: int
    extracted_text: str
    extraction_method: str
    char_count: int
    created_at: datetime


class ExtractedFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    document_type: str
    page_number: int
    extracted_text: str
    confidence_score: float
    created_at: datetime


class DocumentUploadResult(BaseModel):
    uploaded: List[DocumentOut]
    failed: List[dict] = []


class DocumentTextOut(BaseModel):
    document: DocumentOut
    pages: List[DocumentPageOut]
    facts: List[ExtractedFactOut]


CaseDetailOut.model_rebuild()
