"""
Subject To / Conditions Rule Engine.

Menghasilkan daftar kondisi/persyaratan akseptasi (RTC/discount, fire
protection, flood exposure, housekeeping, loss record, security/guarding,
maintenance machinery, exclusion MB/BI/Sharia/Silent Risk, stock
administration clause, acceptance validity, no claim warranty, T&C leader)
berdasarkan KONFIGURASI (subject_to_rules.json) dan DATA (hasil ekstraksi +
riwayat klaim), BUKAN dikarang oleh LLM.

Setiap kondisi yang dihasilkan menyertakan:
 - rule_id & category (dari konfigurasi)
 - text (teks tetap dari konfigurasi rules, tidak diubah/di-generate LLM)
 - triggered_by (field/data yang memicu rule ini, untuk keterlacakan)
 - kb_reference: rujukan Knowledge Base yang paling relevan (jika skor
   similarity memenuhi ambang batas minimum) ATAU penanda eksplisit bahwa
   tidak ditemukan rujukan KB yang relevan (bukan sumber yang dikarang).
"""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.services import kb_service

RULES_PATH = Path(__file__).resolve().parent.parent / "subject_to_rules.json"


def _load_rules() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_value(data: dict, dotted_path: str):
    try:
        cat, field = dotted_path.split(".", 1)
        return data.get(cat, {}).get(field, {}).get("value")
    except (AttributeError, ValueError):
        return None


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "not found", "n/a", "none", "null"):
        return True
    return False


def _condition_matches(extraction_data: dict, has_claims: bool, when: dict) -> bool:
    if when is None:
        return True
    if when.get("source") == "claim_history":
        cond = when.get("condition")
        if cond == "has_claims":
            return has_claims
        if cond == "no_claims":
            return not has_claims
        return False

    field = when.get("field")
    condition = when.get("condition")
    value = _get_value(extraction_data, field) if field else None

    if condition == "value_in":
        targets = [str(t).strip().lower() for t in when.get("values", [])]
        normalized = str(value).strip().lower() if value is not None else ""
        return normalized in targets
    if condition == "not_empty_not_notfound":
        return not _is_missing(value)
    return False


def _find_kb_reference(db: Session, kb_query: str):
    """Cari 1 rujukan KB paling relevan untuk sebuah rule. Mengembalikan dict
    referensi atau None jika tidak ada chunk KB yang cukup relevan."""
    if not kb_query:
        return None
    chunk_rows = db.query(models.KnowledgeChunk).all()
    if not chunk_rows:
        return None
    results = kb_service.search_chunks(kb_query, chunk_rows, top_k=1)
    if not results:
        return None
    top = results[0]
    chunk = top["chunk"]
    doc = chunk.document
    return {
        "document_id": doc.id,
        "document_title": doc.title,
        "document_category": doc.category.value if hasattr(doc.category, "value") else str(doc.category),
        "chunk_index": chunk.chunk_index,
        "excerpt": (chunk.text[:280] + ("..." if len(chunk.text) > 280 else "")),
        "relevance_score": round(top["score"], 4),
    }


def evaluate(db: Session, extraction_data: dict, has_claims: bool) -> list:
    """
    Evaluasi seluruh rule terhadap data ekstraksi & status riwayat klaim.
    Mengembalikan list of dict kondisi Subject To, masing-masing dengan
    rujukan KB (jika ada) - tidak pernah membuat teks kondisi baru di luar
    konfigurasi.
    """
    rules_cfg = _load_rules().get("rules", [])
    results = []

    for rule in rules_cfg:
        always_apply = rule.get("always_apply", False)
        when = rule.get("when")
        triggered = always_apply or _condition_matches(extraction_data, has_claims, when)
        if not triggered:
            continue

        kb_reference = _find_kb_reference(db, rule.get("kb_query"))

        results.append({
            "rule_id": rule["id"],
            "category": rule["category"],
            "text": rule["text_template"],
            "triggered_by": "always_apply" if always_apply else json.dumps(when, ensure_ascii=False),
            "source": "rule_engine:subject_to_rules.json",
            "kb_reference": kb_reference,
            "kb_reference_note": None if kb_reference else "Tidak ditemukan rujukan Knowledge Base yang cukup relevan untuk kondisi ini; kondisi tetap berlaku berdasarkan konfigurasi rule internal (bukan buatan LLM).",
        })

    return results
