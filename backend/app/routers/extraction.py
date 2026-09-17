import json

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app import crud, models
from app.database import get_db
from app.services import llm_client, mock_rules_engine

router = APIRouter(tags=["Structured Data Extraction"])


# ---------------- Helpers ----------------

def _gather_case_documents_payload(db: Session, case_id: str) -> list:
    """Kumpulkan teks hasil ekstraksi (per halaman) dari seluruh dokumen yang
    sudah berstatus Processed pada case ini, untuk dikirim ke LLM Extraction Service."""
    docs = crud.list_documents(db, case_id)
    payload_docs = []
    for d in docs:
        if d.processing_status != models.ProcessingStatus.PROCESSED:
            continue
        pages = crud.get_document_pages(db, d.id)
        if not pages:
            continue
        payload_docs.append({
            "document_id": d.id,
            "filename": d.original_filename,
            "doc_type": d.doc_type.value,
            "pages": [
                {"page_number": p.page_number, "text": p.extracted_text or ""}
                for p in pages
            ],
        })
    return payload_docs


def _next_version_number(db: Session, case_id: str) -> int:
    last = (
        db.query(models.ExtractionVersion)
        .filter(models.ExtractionVersion.case_id == case_id)
        .order_by(models.ExtractionVersion.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


def _version_out(version: models.ExtractionVersion) -> dict:
    return {
        "id": version.id,
        "case_id": version.case_id,
        "version_number": version.version_number,
        "source": version.source.value,
        "method": version.method,
        "model_name": version.model_name,
        "data": json.loads(version.data_json),
        "warnings": json.loads(version.warnings_json or "[]"),
        "created_at": version.created_at.isoformat(),
    }


def _mock_result_out(result: models.MockRulesResult) -> dict:
    return {
        "id": result.id,
        "case_id": result.case_id,
        "extraction_version_id": result.extraction_version_id,
        "risk_level": result.risk_level,
        "risk_flags": json.loads(result.risk_flags_json),
        "missing_critical_info": json.loads(result.missing_critical_json),
        "data_inconsistencies": json.loads(result.inconsistencies_json),
        "recommended_action": result.recommended_action,
        "created_at": result.created_at.isoformat(),
    }


def _latest_version(db: Session, case_id: str):
    return (
        db.query(models.ExtractionVersion)
        .filter(models.ExtractionVersion.case_id == case_id)
        .order_by(models.ExtractionVersion.version_number.desc())
        .first()
    )


# ---------------- Endpoints ----------------

@router.get("/api/llm-service/health")
def llm_service_health():
    """Cek status LLM Extraction Service (dan Ollama di baliknya) dari sisi Main API."""
    return llm_client.check_llm_service_health()


@router.post("/api/cases/{case_id}/extract")
def extract_structured_data(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    documents_payload = _gather_case_documents_payload(db, case_id)
    if not documents_payload:
        raise HTTPException(
            status_code=400,
            detail="Belum ada dokumen berstatus 'Processed' pada case ini. "
                   "Upload & proses dokumen terlebih dahulu sebelum menjalankan ekstraksi.",
        )

    case_context = {
        "quotation_policy_no": case.quotation_policy_no,
        "insured_name": case.insured_name,
        "risk_location": case.risk_location,
        "occupation_business": case.occupation_business,
    }

    try:
        response = llm_client.call_extract({
            "case_id": case_id,
            "case_context": case_context,
            "documents": documents_payload,
        })
    except llm_client.LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    version_number = _next_version_number(db, case_id)
    version = models.ExtractionVersion(
        case_id=case_id,
        version_number=version_number,
        source=models.ExtractionSource.LLM,
        method=response.get("method"),
        model_name=response.get("model"),
        data_json=json.dumps(response["result"]),
        warnings_json=json.dumps(response.get("warnings", [])),
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    crud.add_history(
        db, case_id, "StructuredExtraction",
        description=f"Ekstraksi data terstruktur v{version_number} dibuat "
                    f"(metode: {response.get('method')}, model: {response.get('model')})",
    )

    return _version_out(version)


@router.get("/api/cases/{case_id}/extraction")
def get_latest_extraction(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    version = _latest_version(db, case_id)
    if not version:
        raise HTTPException(status_code=404, detail="Belum ada hasil ekstraksi untuk case ini")
    return _version_out(version)


@router.get("/api/cases/{case_id}/extraction/versions")
def list_extraction_versions(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    versions = (
        db.query(models.ExtractionVersion)
        .filter(models.ExtractionVersion.case_id == case_id)
        .order_by(models.ExtractionVersion.version_number.desc())
        .all()
    )
    return [_version_out(v) for v in versions]


@router.put("/api/cases/{case_id}/extraction")
def save_extraction_edit(case_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    """Simpan hasil edit underwriter sebagai versi baru (append-only)."""
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    data = payload.get("data", payload)  # terima {"data": {...}} atau langsung {...}

    version_number = _next_version_number(db, case_id)
    version = models.ExtractionVersion(
        case_id=case_id,
        version_number=version_number,
        source=models.ExtractionSource.UNDERWRITER_EDIT,
        method="underwriter_edit",
        model_name=None,
        data_json=json.dumps(data),
        warnings_json="[]",
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    crud.add_history(
        db, case_id, "ExtractionEdited",
        description=f"Data hasil ekstraksi diedit & disimpan oleh underwriter (v{version_number})",
    )

    return _version_out(version)


@router.post("/api/cases/{case_id}/mock-rules")
def submit_mock_rules(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    version = _latest_version(db, case_id)
    if not version:
        raise HTTPException(
            status_code=400,
            detail="Belum ada data hasil ekstraksi untuk case ini. Jalankan ekstraksi terlebih dahulu.",
        )

    data = json.loads(version.data_json)
    evaluation = mock_rules_engine.evaluate(data)

    result = models.MockRulesResult(
        case_id=case_id,
        extraction_version_id=version.id,
        risk_level=evaluation["risk_level"],
        risk_flags_json=json.dumps(evaluation["risk_flags"]),
        missing_critical_json=json.dumps(evaluation["missing_critical_info"]),
        inconsistencies_json=json.dumps(evaluation["data_inconsistencies"]),
        recommended_action=evaluation["recommended_action"],
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    crud.add_history(
        db, case_id, "MockRulesEvaluated",
        description=f"Mock rules dijalankan terhadap extraction v{version.version_number} "
                    f"-> risk level: {evaluation['risk_level']}",
    )

    return _mock_result_out(result)


@router.get("/api/cases/{case_id}/mock-rules")
def get_latest_mock_rules(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    result = (
        db.query(models.MockRulesResult)
        .filter(models.MockRulesResult.case_id == case_id)
        .order_by(models.MockRulesResult.created_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Belum ada hasil mock rules untuk case ini")
    return _mock_result_out(result)
