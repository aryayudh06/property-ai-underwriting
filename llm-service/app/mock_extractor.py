"""
Mode mock: mengekstrak data secara heuristik (pencocokan kata kunci sederhana),
digunakan sebagai fallback jika Ollama tidak tersedia. Ini BUKAN LLM/AI generatif -
sekadar agar prototype tetap bisa didemokan end-to-end tanpa dependency eksternal.
Field yang tidak berhasil dicocokkan akan dilengkapi menjadi "Not Found" oleh
fungsi repair_result() di extraction_service.py.
"""
import re
from typing import List

from app.schemas import DocumentInput

# (kategori, field) -> (daftar keyword, nilai yang diisi jika ditemukan)
KEYWORD_HINTS = {
    ("fire_protection", "sprinkler"): (["sprinkler"], "Ada"),
    ("fire_protection", "hydrant"): (["hydrant"], "Ada"),
    ("fire_protection", "fire_alarm"): (["fire alarm", "alarm kebakaran"], "Ada"),
    ("fire_protection", "apar_fire_extinguisher"): (
        ["apar", "fire extinguisher", "pemadam api ringan"], "Ada"
    ),
    ("natural_perils", "flood_risk"): (["banjir", "flood"], "Disebutkan dalam dokumen"),
    ("natural_perils", "earthquake_risk"): (["gempa", "earthquake"], "Disebutkan dalam dokumen"),
    ("natural_perils", "windstorm_risk"): (["angin ribut", "badai", "windstorm"], "Disebutkan dalam dokumen"),
    ("building", "construction_type"): (["beton", "baja", "concrete", "steel"], None),  # nilai diambil dari keyword yg cocok
    ("loss_history", "previous_claims"): (["klaim sebelumnya", "riwayat klaim", "previous claim"], "Disebutkan dalam dokumen"),
    ("survey", "surveyor_name"): (["surveyor"], "Disebutkan dalam dokumen"),
    ("occupancy", "occupation_type"): (["pabrik", "gudang", "hotel", "kantor", "pergudangan"], None),
}

MONEY_PATTERN = re.compile(r"rp[\s.]*([\d][\d.,]{5,})", re.IGNORECASE)


def _snippet(text: str, keyword: str, width: int = 90) -> str:
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return text.strip()[:180]
    start = max(0, idx - width // 2)
    end = min(len(text), idx + width)
    return text[start:end].strip()


def build_mock_result(documents: List[DocumentInput]) -> dict:
    flat_pages = []  # list of (DocumentInput, DocumentPageInput)
    for doc in documents:
        for page in doc.pages:
            flat_pages.append((doc, page))

    def find_source(keyword: str):
        for doc, page in flat_pages:
            if keyword.lower() in (page.text or "").lower():
                return doc, page
        return None, None

    result = {}

    for (cat, field), (keywords, fixed_value) in KEYWORD_HINTS.items():
        result.setdefault(cat, {})
        matched_doc = matched_page = matched_kw = None
        for kw in keywords:
            d, p = find_source(kw)
            if d:
                matched_doc, matched_page, matched_kw = d, p, kw
                break
        if matched_doc:
            value = fixed_value if fixed_value is not None else matched_kw.title()
            result[cat][field] = {
                "value": value,
                "source_document": matched_doc.filename,
                "page": matched_page.page_number,
                "evidence": _snippet(matched_page.text, matched_kw),
                "confidence": 0.55,
            }

    # Coba temukan angka nominal (Rp ...) untuk sum insured
    for doc, page in flat_pages:
        match = MONEY_PATTERN.search(page.text or "")
        if match:
            value = f"Rp {match.group(1)}"
            field_data = {
                "value": value,
                "source_document": doc.filename,
                "page": page.page_number,
                "evidence": _snippet(page.text, "rp"),
                "confidence": 0.5,
            }
            result.setdefault("assets", {})["sum_insured_total"] = field_data
            result.setdefault("coverage", {})["sum_insured"] = dict(field_data)
            break

    result["data_gaps"] = []
    result["conflicts"] = []
    result["sources"] = [
        {"document_id": doc.document_id, "filename": doc.filename,
         "pages": [p.page_number for d2, p in flat_pages if d2.document_id == doc.document_id]}
        for doc in documents
    ]
    result["confidence"] = 0.0  # dihitung ulang di repair_result berdasarkan field yang terisi

    return result
