"""
Layanan pemrosesan dokumen:
 - Ekstraksi teks PDF menggunakan PyMuPDF (fitz)
 - Fallback OCR (Tesseract) jika teks PDF tidak tersedia/tidak memadai
 - OCR langsung untuk file gambar (JPG/PNG)
 - Klasifikasi jenis dokumen berbasis kata kunci sederhana (heuristik, bukan LLM/rules engine)
"""
from app.config import MIN_TEXT_LENGTH_THRESHOLD
from app.models import DocumentType
from app.services import ocr_service

CLASSIFICATION_KEYWORDS = {
    DocumentType.QUOTATION_SLIP: [
        "quotation slip", "quotation", "penawaran", "premi", "polis no", "insured"
    ],
    DocumentType.LEMBAR_ANALISA: [
        "lembar analisa", "analisa risiko", "risk analysis", "underwriting analysis"
    ],
    DocumentType.SURVEY_REPORT: [
        "survey report", "laporan survey", "site survey", "risk survey", "surveyor"
    ],
    DocumentType.DATA_ASET: [
        "data aset", "asset list", "daftar aset", "sum insured", "nilai pertanggungan"
    ],
    DocumentType.DOKUMEN_PENDUKUNG: [
        "lampiran", "dokumen pendukung", "supporting document", "surat"
    ],
}


def classify_document(all_text: str) -> DocumentType:
    text_lower = (all_text or "").lower()
    if not text_lower.strip():
        return DocumentType.UNKNOWN

    scores = {doc_type: 0 for doc_type in CLASSIFICATION_KEYWORDS}
    for doc_type, keywords in CLASSIFICATION_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[doc_type] += 1

    best_type = max(scores, key=scores.get)
    if scores[best_type] == 0:
        return DocumentType.UNKNOWN
    return best_type


def extract_pdf(file_path: str):
    """
    Ekstraksi teks PDF per halaman.
    Mengembalikan (pages: List[dict], full_text: str)
    dict page = {page_number, extracted_text, extraction_method, char_count}
    """
    import fitz  # PyMuPDF

    pages = []
    full_text_parts = []

    doc = fitz.open(file_path)
    try:
        for i, page in enumerate(doc, start=1):
            text = (page.get_text() or "").strip()
            method = "text"

            if len(text) < MIN_TEXT_LENGTH_THRESHOLD:
                # teks tidak tersedia / tidak memadai -> gunakan OCR
                try:
                    ocr_text = ocr_service.ocr_pdf_page(page).strip()
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        method = "ocr"
                except Exception as e:
                    if not text:
                        text = f"[OCR gagal: {e}]"
                        method = "ocr_failed"

            pages.append({
                "page_number": i,
                "extracted_text": text,
                "extraction_method": method,
                "char_count": len(text),
            })
            full_text_parts.append(text)
    finally:
        doc.close()

    return pages, "\n".join(full_text_parts)


def extract_image(file_path: str):
    """Ekstraksi teks dari file gambar (JPG/PNG) menggunakan OCR langsung."""
    with open(file_path, "rb") as f:
        raw = f.read()

    method = "ocr"
    try:
        text = ocr_service.ocr_image_bytes(raw).strip()
    except Exception as e:
        text = f"[OCR gagal: {e}]"
        method = "ocr_failed"

    pages = [{
        "page_number": 1,
        "extracted_text": text,
        "extraction_method": method,
        "char_count": len(text),
    }]
    return pages, text


def get_pdf_page_count(file_path: str) -> int:
    import fitz
    doc = fitz.open(file_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def build_facts_from_pages(pages: list, doc_type: str):
    """Bangun daftar 'extracted facts' (kutipan/fakta) per halaman, dapat ditelusuri."""
    facts = []
    for p in pages:
        text = p["extracted_text"].strip()
        if not text:
            continue
        snippet = text[:500]
        confidence = {
            "text": 0.95,
            "ocr": 0.75,
            "ocr_failed": 0.0,
        }.get(p["extraction_method"], 0.5)

        facts.append({
            "document_type": doc_type,
            "page_number": p["page_number"],
            "extracted_text": snippet,
            "confidence_score": confidence,
        })
    return facts
