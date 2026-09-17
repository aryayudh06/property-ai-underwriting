import json

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app import crud, models
from app.database import get_db
from app.services import disposition_service, rag_answer_service, regional_risk_service

router = APIRouter(tags=["Disposisi Underwriting"])


def _disposition_out(d: models.CaseDisposition) -> dict:
    return {
        "id": d.id,
        "case_id": d.case_id,
        "version_number": d.version_number,
        "source": d.source,
        "toc": d.toc,
        "tsi_override": d.tsi_override,
        "loss_ratio": d.loss_ratio,
        "poi_override": d.poi_override,
        "placement_share_plan": d.placement_share_plan,
        "placement_leader": d.placement_leader,
        "placement_proposed_participation": d.placement_proposed_participation,
        "uw_decision": d.uw_decision,
        "uw_conditions_warranty": d.uw_conditions_warranty,
        "uw_exclusions": d.uw_exclusions,
        "uw_special_terms": d.uw_special_terms,
        "subject_to": json.loads(d.subject_to_json or "[]"),
        "underwriter_notes": d.underwriter_notes,
        "coordination_notes": d.coordination_notes,
        "kb_references": json.loads(d.kb_references_json or "[]"),
        "disposition_text": d.disposition_text,
        "created_at": d.created_at.isoformat(),
    }


def _next_version_number(db: Session, case_id: str) -> int:
    last = (
        db.query(models.CaseDisposition)
        .filter(models.CaseDisposition.case_id == case_id)
        .order_by(models.CaseDisposition.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


def _latest_disposition(db: Session, case_id: str):
    return (
        db.query(models.CaseDisposition)
        .filter(models.CaseDisposition.case_id == case_id)
        .order_by(models.CaseDisposition.version_number.desc())
        .first()
    )


@router.post("/api/cases/{case_id}/disposition/generate")
def generate_disposition(case_id: str, payload: dict = Body(default={}), db: Session = Depends(get_db)):
    """
    Menyusun Disposisi Underwriting secara otomatis dengan menggabungkan:
    data case & hasil ekstraksi, hasil search riwayat klaim (fitur lanjutan #1),
    hasil Subject To/Conditions rule engine + rujukan RAG Knowledge Base
    (fitur lanjutan #2), dan pengecekan koordinasi antar cabang. Hasil akhir
    berupa teks disposisi yang tetap dapat diedit oleh underwriter.
    """
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    overrides = payload.get("overrides", payload) or {}
    struct = disposition_service.generate_disposition_data(db, case, overrides)
    disposition_text = disposition_service.render_disposition_text(struct)

    version_number = _next_version_number(db, case_id)
    d = models.CaseDisposition(
        case_id=case_id,
        version_number=version_number,
        source="generated",
        toc=struct["risk_info"]["toc"],
        tsi_override=str(struct["risk_info"]["tsi"]),
        loss_ratio=struct["risk_info"]["loss_ratio"],
        poi_override=struct["risk_info"]["poi"],
        placement_share_plan=struct["placement_info"]["share_plan"],
        placement_leader=struct["placement_info"]["leader"],
        placement_proposed_participation=struct["placement_info"]["proposed_participation"],
        uw_decision=struct["recommendation"]["decision"],
        uw_conditions_warranty=struct["recommendation"]["conditions_warranty"],
        uw_exclusions=struct["recommendation"]["exclusions"],
        uw_special_terms=struct["recommendation"]["special_terms"],
        subject_to_json=json.dumps(struct["subject_to"], ensure_ascii=False),
        underwriter_notes=struct["underwriter_notes"],
        coordination_notes=struct["coordination"]["note"],
        kb_references_json=json.dumps(struct["kb_references"], ensure_ascii=False),
        disposition_text=disposition_text,
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    crud.add_history(
        db, case_id, "DispositionGenerated",
        description=f"Disposisi underwriting v{version_number} disusun otomatis "
                    f"(rule engine + RAG KB + search klaim).",
    )

    return _disposition_out(d)


@router.get("/api/cases/{case_id}/disposition")
def get_latest_disposition(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    d = _latest_disposition(db, case_id)
    if not d:
        raise HTTPException(status_code=404, detail="Belum ada disposisi untuk case ini")
    return _disposition_out(d)


@router.get("/api/cases/{case_id}/disposition/versions")
def list_disposition_versions(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    versions = (
        db.query(models.CaseDisposition)
        .filter(models.CaseDisposition.case_id == case_id)
        .order_by(models.CaseDisposition.version_number.desc())
        .all()
    )
    return [_disposition_out(v) for v in versions]


@router.put("/api/cases/{case_id}/disposition")
def save_disposition_edit(case_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    """Simpan hasil edit underwriter atas teks disposisi (append-only versi baru)."""
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    latest = _latest_disposition(db, case_id)
    if not latest:
        raise HTTPException(
            status_code=400,
            detail="Belum ada disposisi untuk case ini. Jalankan generate terlebih dahulu.",
        )

    disposition_text = payload.get("disposition_text")
    if disposition_text is None:
        raise HTTPException(status_code=400, detail="Field 'disposition_text' wajib diisi.")

    version_number = _next_version_number(db, case_id)
    d = models.CaseDisposition(
        case_id=case_id,
        version_number=version_number,
        source="underwriter_edit",
        toc=latest.toc,
        tsi_override=latest.tsi_override,
        loss_ratio=latest.loss_ratio,
        poi_override=latest.poi_override,
        placement_share_plan=latest.placement_share_plan,
        placement_leader=latest.placement_leader,
        placement_proposed_participation=latest.placement_proposed_participation,
        uw_decision=latest.uw_decision,
        uw_conditions_warranty=latest.uw_conditions_warranty,
        uw_exclusions=latest.uw_exclusions,
        uw_special_terms=latest.uw_special_terms,
        subject_to_json=latest.subject_to_json,
        underwriter_notes=payload.get("underwriter_notes", latest.underwriter_notes),
        coordination_notes=latest.coordination_notes,
        kb_references_json=latest.kb_references_json,
        disposition_text=disposition_text,
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    crud.add_history(
        db, case_id, "DispositionEdited",
        description=f"Teks disposisi diedit & disimpan oleh underwriter (v{version_number})",
    )

    return _disposition_out(d)


@router.post("/api/cases/{case_id}/disposition/narrative")
def generate_disposition_narrative(case_id: str, db: Session = Depends(get_db)):
    """
    Fitur RAG generatif penuh untuk Disposisi: CONTEXT INJECTION dari kondisi
    Subject To/Conditions (rule engine) + kutipan Knowledge Base yang sudah
    dirujuk masing-masing kondisi → GEMINI (via LLM Service /rag/answer)
    menyusun narasi ringkas. Hasil ini hanya SARAN teks yang bisa
    disalin/disisipkan underwriter ke dalam Catatan Underwriter / disposisi -
    TIDAK menggantikan atau mengubah keputusan/kondisi dari rule engine.
    """
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    latest = _latest_disposition(db, case_id)
    if not latest:
        raise HTTPException(
            status_code=400,
            detail="Belum ada disposisi untuk case ini. Jalankan generate terlebih dahulu.",
        )

    subject_to = json.loads(latest.subject_to_json or "[]")
    if not subject_to:
        raise HTTPException(status_code=400, detail="Tidak ada kondisi Subject To/Conditions untuk dinarasikan.")

    case_context = {
        "insured_name": case.insured_name,
        "occupation_business": case.occupation_business,
    }

    try:
        result = rag_answer_service.narrate_subject_to(db, subject_to, case_context=case_context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal menyusun narasi AI: {e}")

    return result


@router.get("/api/cases/{case_id}/qualitative-analysis")
async def get_qualitative_analysis(case_id: str, db: Session = Depends(get_db)):
    """
    Analisis Kualitatif: merangkum SELURUH hasil Disposisi Underwriting versi
    terbaru (Informasi Risiko, Riwayat Klaim, Subject To/Conditions, Rekomendasi,
    Koordinasi Cabang) digabung dengan Analisis Risiko Bencana Wilayah atas
    Lokasi Risiko case ini (regional_risk_service.py - web scraping Google
    News RSS + keyword heuristic). Murni agregasi data yang sudah ada + hasil
    scraping nyata - TIDAK menggunakan LLM.
    """
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    latest = _latest_disposition(db, case_id)
    if not latest:
        raise HTTPException(
            status_code=400,
            detail="Belum ada disposisi untuk case ini. Jalankan Generate Disposisi terlebih dahulu.",
        )

    regional_risk = await regional_risk_service.analyze_regional_disaster_risk(case.risk_location)
    return disposition_service.build_qualitative_analysis_data(db, case, latest, regional_risk)
