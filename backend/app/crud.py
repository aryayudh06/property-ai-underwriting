from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models, schemas


# ---------------- Case History ----------------

def add_history(
    db: Session,
    case_id: str,
    action: str,
    description: str = None,
    old_value: str = None,
    new_value: str = None,
):
    entry = models.CaseHistory(
        case_id=case_id,
        action=action,
        description=description,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------- Case ----------------

def create_case(db: Session, payload: schemas.CaseCreate) -> models.Case:
    case = models.Case(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    add_history(
        db, case.id, "Created",
        description=f"Case dibuat untuk tertanggung '{case.insured_name}'",
    )
    return case


def get_case(db: Session, case_id: str) -> Optional[models.Case]:
    return db.query(models.Case).filter(models.Case.id == case_id).first()


def list_cases(db: Session, status: Optional[str] = None, search: Optional[str] = None):
    q = db.query(models.Case)
    if status:
        q = q.filter(models.Case.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (models.Case.insured_name.ilike(like))
            | (models.Case.quotation_policy_no.ilike(like))
            | (models.Case.risk_location.ilike(like))
        )
    return q.order_by(models.Case.created_at.desc()).all()


def update_case(db: Session, case: models.Case, payload: schemas.CaseUpdate) -> models.Case:
    changes = []
    data = payload.model_dump(exclude_unset=True)
    for field, new_val in data.items():
        old_val = getattr(case, field)
        if str(old_val) != str(new_val) and new_val is not None:
            changes.append((field, old_val, new_val))
            setattr(case, field, new_val)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)

    if changes:
        desc = "; ".join([f"{f}: '{o}' -> '{n}'" for f, o, n in changes])
        action = "StatusChanged" if len(changes) == 1 and changes[0][0] == "status" else "Updated"
        add_history(
            db, case.id, action,
            description=desc,
            old_value=str(changes[0][1]) if len(changes) == 1 else None,
            new_value=str(changes[0][2]) if len(changes) == 1 else None,
        )
    return case


def delete_case(db: Session, case: models.Case):
    db.delete(case)
    db.commit()


# ---------------- Document ----------------

def create_document(db: Session, document: models.Document) -> models.Document:
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, document_id: str) -> Optional[models.Document]:
    return db.query(models.Document).filter(models.Document.id == document_id).first()


def list_documents(db: Session, case_id: str):
    return (
        db.query(models.Document)
        .filter(models.Document.case_id == case_id)
        .order_by(models.Document.uploaded_at.desc())
        .all()
    )


def replace_document_pages(db: Session, document_id: str, pages_data: list):
    db.query(models.DocumentPage).filter(
        models.DocumentPage.document_id == document_id
    ).delete()
    for p in pages_data:
        db.add(models.DocumentPage(document_id=document_id, **p))
    db.commit()


def replace_extracted_facts(db: Session, document_id: str, facts_data: list):
    db.query(models.ExtractedFact).filter(
        models.ExtractedFact.document_id == document_id
    ).delete()
    for f in facts_data:
        db.add(models.ExtractedFact(document_id=document_id, **f))
    db.commit()


def get_document_pages(db: Session, document_id: str):
    return (
        db.query(models.DocumentPage)
        .filter(models.DocumentPage.document_id == document_id)
        .order_by(models.DocumentPage.page_number)
        .all()
    )


def get_document_facts(db: Session, document_id: str):
    return (
        db.query(models.ExtractedFact)
        .filter(models.ExtractedFact.document_id == document_id)
        .all()
    )
