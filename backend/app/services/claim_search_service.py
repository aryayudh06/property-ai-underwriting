"""
Search riwayat klaim Tertanggung (PT) pada database dummy SQLite (claim_history).
Murni query database (LIKE/ILIKE pencocokan nama), TIDAK menggunakan LLM sama sekali.
Pada implementasi produksi, tabel ini akan digantikan oleh koneksi ke sistem
data warehouse klaim perusahaan yang sesungguhnya.
"""
from sqlalchemy.orm import Session

from app import models


def search_claims_by_insured_name(db: Session, insured_name: str, limit: int = 50):
    """Cari riwayat klaim berdasarkan kecocokan sebagian nama Tertanggung (case-insensitive)."""
    if not insured_name or not insured_name.strip():
        return []
    like = f"%{insured_name.strip()}%"
    return (
        db.query(models.ClaimHistory)
        .filter(models.ClaimHistory.insured_name.ilike(like))
        .order_by(models.ClaimHistory.loss_date.desc())
        .limit(limit)
        .all()
    )


def claim_out(c: models.ClaimHistory) -> dict:
    return {
        "id": c.id,
        "insured_name": c.insured_name,
        "policy_no": c.policy_no,
        "class_of_business": c.class_of_business,
        "branch": c.branch,
        "loss_date": c.loss_date,
        "cause_of_loss": c.cause_of_loss,
        "tsi_at_loss": c.tsi_at_loss,
        "claim_amount": c.claim_amount,
        "claim_status": c.claim_status,
        "notes": c.notes,
    }
