import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_case_id():
    return f"CASE-{uuid.uuid4().hex[:8].upper()}"


def gen_uuid():
    return uuid.uuid4().hex


class CaseStatus(str, enum.Enum):
    DRAFT = "Draft"
    PROCESSING = "Processing"
    REVIEWED = "Reviewed"
    COMPLETED = "Completed"


class DocumentType(str, enum.Enum):
    QUOTATION_SLIP = "Quotation Slip"
    LEMBAR_ANALISA = "Lembar Analisa"
    SURVEY_REPORT = "Survey Report"
    DATA_ASET = "Data Aset"
    DOKUMEN_PENDUKUNG = "Dokumen Pendukung"
    UNKNOWN = "Unknown"


class ProcessingStatus(str, enum.Enum):
    UPLOADED = "Uploaded"
    PROCESSING = "Processing"
    PROCESSED = "Processed"
    FAILED = "Failed"


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=gen_case_id)
    quotation_policy_no = Column(String, nullable=False)
    insured_name = Column(String, nullable=False)
    risk_location = Column(String, nullable=False)
    occupation_business = Column(String, nullable=False)
    period_start = Column(String, nullable=True)  # ISO date string
    period_end = Column(String, nullable=True)
    branch = Column(String, nullable=True)  # Kantor/cabang pengaju - untuk pengecekan koordinasi antar cabang
    status = Column(Enum(CaseStatus), default=CaseStatus.DRAFT, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    history = relationship(
        "CaseHistory", back_populates="case", cascade="all, delete-orphan",
        order_by="desc(CaseHistory.created_at)"
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)

    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)

    doc_type = Column(Enum(DocumentType), default=DocumentType.UNKNOWN, nullable=False)
    file_format = Column(String, nullable=False)  # pdf / jpg / png
    file_size = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.UPLOADED)
    processing_error = Column(Text, nullable=True)

    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="documents")
    pages = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan",
        order_by="DocumentPage.page_number"
    )
    facts = relationship(
        "ExtractedFact", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    extracted_text = Column(Text, default="")
    extraction_method = Column(String, default="text")  # "text" atau "ocr"
    char_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="pages")


class ExtractedFact(Base):
    """Sumber fakta yang dapat ditelusuri ke dokumen & halaman asal."""
    __tablename__ = "extracted_facts"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    document_type = Column(String, nullable=False)
    page_number = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="facts")


class CaseHistory(Base):
    __tablename__ = "case_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    action = Column(String, nullable=False)  # Created, Updated, StatusChanged, DocumentUploaded, DocumentProcessed...
    description = Column(Text, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="history")


class ExtractionSource(str, enum.Enum):
    LLM = "llm"
    UNDERWRITER_EDIT = "underwriter_edit"


class ExtractionVersion(Base):
    """
    Satu baris = satu versi hasil ekstraksi data terstruktur untuk sebuah case.
    Setiap kali LLM dijalankan (extract/re-extract) atau underwriter menyimpan
    perubahan, versi baru dibuat (append-only) sehingga histori tetap terlacak.
    """
    __tablename__ = "extraction_versions"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    source = Column(Enum(ExtractionSource), nullable=False)
    method = Column(String, nullable=True)  # ollama / mock / mock_fallback / underwriter_edit
    model_name = Column(String, nullable=True)
    data_json = Column(Text, nullable=False)  # ExtractionResult tersimpan sebagai JSON
    warnings_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case")


class MockRulesResult(Base):
    """Hasil evaluasi mock rule engine terhadap satu versi hasil ekstraksi."""
    __tablename__ = "mock_rules_results"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    extraction_version_id = Column(String, ForeignKey("extraction_versions.id"), nullable=False)
    risk_level = Column(String, nullable=False)
    risk_flags_json = Column(Text, nullable=False)
    missing_critical_json = Column(Text, nullable=False)
    inconsistencies_json = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case")


# =====================================================================
# FITUR LANJUTAN: (1) Search Riwayat Klaim, (2) RAG Knowledge Base,
# (3) Subject-To/Conditions Rule Engine, (4) Disposisi Underwriting
# =====================================================================

class ClaimHistory(Base):
    """
    Dummy database riwayat klaim (SQLite) untuk pencarian riwayat klaim per
    Tertanggung (PT). Data bersifat dummy/contoh untuk keperluan prototipe -
    pada implementasi produksi, sumber data ini akan berasal dari sistem klaim
    perusahaan (data warehouse klaim), bukan dibuat oleh LLM.
    """
    __tablename__ = "claim_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    insured_name = Column(String, nullable=False, index=True)
    policy_no = Column(String, nullable=True)
    class_of_business = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    loss_date = Column(String, nullable=True)
    cause_of_loss = Column(String, nullable=True)
    tsi_at_loss = Column(String, nullable=True)
    claim_amount = Column(String, nullable=True)
    claim_status = Column(String, nullable=True)  # Settled / Open / Repudiated
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeCategory(str, enum.Enum):
    PEDOMAN_UNDERWRITING = "Pedoman Underwriting"
    SOP = "SOP"
    RISK_APPETITE = "Risk Appetite"
    MANUAL_RISIKO = "Manual Risiko"
    KETENTUAN_PRODUK = "Ketentuan Produk"
    TEMPLATE_DISPOSISI = "Template Disposisi"
    LAINNYA = "Lainnya"


class KnowledgeDocument(Base):
    """Metadata dokumen pengetahuan (pedoman/SOP/risk appetite/dst) yang diindeks untuk RAG."""
    __tablename__ = "knowledge_documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    category = Column(Enum(KnowledgeCategory), default=KnowledgeCategory.LAINNYA, nullable=False)
    original_filename = Column(String, nullable=True)
    file_format = Column(String, nullable=True)
    full_text = Column(Text, nullable=False, default="")
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """
    Satu potongan (chunk) teks dari dokumen KB beserta embedding vektornya.
    Berperan sebagai 'vector database' sederhana (disimpan di SQLite,
    similarity dihitung di aplikasi) untuk pencarian RAG (retrieval).
    """
    __tablename__ = "knowledge_chunks"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("knowledge_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=False)  # JSON list[float]
    char_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("KnowledgeDocument", back_populates="chunks")


class CaseDisposition(Base):
    """
    Satu baris = satu versi Disposisi Underwriting untuk sebuah case (append-only,
    sama seperti ExtractionVersion) - berisi Informasi Risiko, Informasi Placement,
    Rekomendasi Underwriting, Subject To/Conditions (hasil rule engine, BUKAN buatan
    LLM), Catatan Underwriter, referensi Knowledge Base yang dipakai, dan
    teks disposisi final yang dapat diedit oleh underwriter.
    """
    __tablename__ = "case_dispositions"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    source = Column(String, default="generated")  # generated / underwriter_edit

    # Informasi Risiko (sebagian bisa override manual dari underwriter)
    toc = Column(String, nullable=True)  # Type of Cover
    tsi_override = Column(String, nullable=True)
    loss_ratio = Column(String, nullable=True)
    poi_override = Column(String, nullable=True)

    # Informasi Placement
    placement_share_plan = Column(String, nullable=True)
    placement_leader = Column(String, nullable=True)
    placement_proposed_participation = Column(String, nullable=True)

    # Rekomendasi Underwriting
    uw_decision = Column(String, nullable=True)
    uw_conditions_warranty = Column(Text, nullable=True)
    uw_exclusions = Column(Text, nullable=True)
    uw_special_terms = Column(Text, nullable=True)

    # Subject To / Conditions - hasil rule engine (JSON list of {rule_id, category, text, source})
    subject_to_json = Column(Text, nullable=False, default="[]")

    # Catatan Underwriter
    underwriter_notes = Column(Text, nullable=True)
    coordination_notes = Column(Text, nullable=True)

    # Referensi Knowledge Base yang dipakai (JSON list)
    kb_references_json = Column(Text, nullable=False, default="[]")

    # Teks disposisi final tersusun, dapat diedit bebas oleh underwriter
    disposition_text = Column(Text, nullable=False, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case")
