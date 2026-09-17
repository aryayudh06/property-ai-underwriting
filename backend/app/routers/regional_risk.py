from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.services import regional_risk_service

router = APIRouter(tags=["Analisis Risiko Bencana Wilayah"])


@router.get("/api/cases/{case_id}/regional-risk")
async def get_regional_disaster_risk(
    case_id: str,
    limit: int = Query(5, ge=1, le=15),
    db: Session = Depends(get_db),
):
    """
    Fitur Lanjutan: Analisis Risiko Bencana Wilayah atas Lokasi Risiko case ini.
    Scraping berita publik terkini (Google News RSS) terkait bencana/gangguan
    kondisi wilayah (banjir, gempa, kebakaran hutan, longsor, kerusuhan, konflik
    lahan, pemadaman listrik, dst), murni web scraping + keyword heuristic -
    TIDAK menggunakan LLM/model AI.
    """
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    result = await regional_risk_service.analyze_regional_disaster_risk(case.risk_location, limit=limit)
    return {"case_id": case_id, **result}
