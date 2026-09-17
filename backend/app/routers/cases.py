from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/cases", tags=["Case Management"])


def _case_out(case) -> schemas.CaseOut:
    out = schemas.CaseOut.model_validate(case)
    out.document_count = len(case.documents)
    return out


@router.post("", response_model=schemas.CaseOut, status_code=201)
def create_case(payload: schemas.CaseCreate, db: Session = Depends(get_db)):
    case = crud.create_case(db, payload)
    return _case_out(case)


@router.get("", response_model=List[schemas.CaseOut])
def list_cases(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    cases = crud.list_cases(db, status=status, search=search)
    return [_case_out(c) for c in cases]


@router.get("/{case_id}", response_model=schemas.CaseDetailOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    out = schemas.CaseDetailOut.model_validate(case)
    out.document_count = len(case.documents)
    return out


@router.put("/{case_id}", response_model=schemas.CaseOut)
def update_case(case_id: str, payload: schemas.CaseUpdate, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    case = crud.update_case(db, case, payload)
    return _case_out(case)


@router.patch("/{case_id}/status", response_model=schemas.CaseOut)
def change_status(case_id: str, payload: schemas.CaseStatusUpdate, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    case = crud.update_case(db, case, schemas.CaseUpdate(status=payload.status))
    return _case_out(case)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    crud.delete_case(db, case)
    return None


@router.get("/{case_id}/history", response_model=List[schemas.CaseHistoryOut])
def get_case_history(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    return case.history
