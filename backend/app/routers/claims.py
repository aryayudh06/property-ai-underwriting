from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.services import claim_search_service

router = APIRouter(tags=["Claim History Search"])


@router.get("/api/claims/search")
def search_claims(insured_name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Fitur Lanjutan #1: Search database SQLite dummy untuk mencari riwayat klaim
    berdasarkan nama Tertanggung (PT). Murni query database, tanpa LLM.
    """
    claims = claim_search_service.search_claims_by_insured_name(db, insured_name)
    return {
        "query": insured_name,
        "count": len(claims),
        "results": [claim_search_service.claim_out(c) for c in claims],
    }


@router.get("/api/cases/{case_id}/claims-search")
def search_claims_for_case(case_id: str, db: Session = Depends(get_db)):
    """Shortcut: cari riwayat klaim berdasarkan nama Tertanggung pada case ini."""
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    claims = claim_search_service.search_claims_by_insured_name(db, case.insured_name)
    return {
        "case_id": case_id,
        "insured_name": case.insured_name,
        "count": len(claims),
        "results": [claim_search_service.claim_out(c) for c in claims],
    }
