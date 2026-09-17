from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db
from app.services import file_storage, document_processor

router = APIRouter(tags=["Document Processing"])


def _process_document(db: Session, document: models.Document):
    """Jalankan ekstraksi teks (+ OCR fallback) dan klasifikasi untuk satu dokumen."""
    document.processing_status = models.ProcessingStatus.PROCESSING
    db.commit()

    try:
        if document.file_format == "pdf":
            document.page_count = document_processor.get_pdf_page_count(document.storage_path)
            pages, full_text = document_processor.extract_pdf(document.storage_path)
        else:
            document.page_count = 1
            pages, full_text = document_processor.extract_image(document.storage_path)

        doc_type = document_processor.classify_document(full_text)
        document.doc_type = doc_type

        crud.replace_document_pages(db, document.id, pages)
        facts = document_processor.build_facts_from_pages(pages, doc_type.value)
        crud.replace_extracted_facts(db, document.id, facts)

        document.processing_status = models.ProcessingStatus.PROCESSED
        document.processing_error = None
        document.processed_at = datetime.utcnow()
    except Exception as e:
        document.processing_status = models.ProcessingStatus.FAILED
        document.processing_error = str(e)

    db.commit()
    db.refresh(document)

    crud.add_history(
        db, document.case_id, "DocumentProcessed",
        description=f"Dokumen '{document.original_filename}' diproses -> "
                    f"{document.processing_status.value} (tipe: {document.doc_type.value})",
    )
    return document


@router.post(
    "/api/cases/{case_id}/documents",
    response_model=schemas.DocumentUploadResult,
    status_code=201,
)
async def upload_documents(
    case_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")

    uploaded = []
    failed = []

    for f in files:
        try:
            raw = await f.read()
            file_storage.validate_upload(f, len(raw))
            saved = file_storage.save_upload_file(case_id, f, raw)

            document = models.Document(
                case_id=case_id,
                original_filename=f.filename,
                stored_filename=saved["stored_filename"],
                storage_path=saved["storage_path"],
                file_format=saved["file_format"],
                file_size=saved["file_size"],
                doc_type=models.DocumentType.UNKNOWN,
                processing_status=models.ProcessingStatus.UPLOADED,
            )
            document = crud.create_document(db, document)

            crud.add_history(
                db, case_id, "DocumentUploaded",
                description=f"Dokumen '{f.filename}' diunggah ({saved['file_size']} bytes)",
            )

            # otomatis proses langsung setelah upload
            document = _process_document(db, document)
            uploaded.append(document)

        except file_storage.UploadValidationError as e:
            failed.append({"filename": f.filename, "error": str(e)})
        except Exception as e:
            failed.append({"filename": f.filename, "error": f"Gagal memproses: {e}"})

    return schemas.DocumentUploadResult(uploaded=uploaded, failed=failed)


@router.get("/api/cases/{case_id}/documents", response_model=List[schemas.DocumentOut])
def list_case_documents(case_id: str, db: Session = Depends(get_db)):
    case = crud.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case tidak ditemukan")
    return crud.list_documents(db, case_id)


@router.get("/api/documents/{document_id}", response_model=schemas.DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    return document


@router.get("/api/documents/{document_id}/preview")
def preview_document(document_id: str, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File fisik tidak ditemukan di storage")

    media_types = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    media_type = media_types.get(document.file_format, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=document.original_filename)


@router.get("/api/documents/{document_id}/text", response_model=schemas.DocumentTextOut)
def get_document_text(document_id: str, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    pages = crud.get_document_pages(db, document_id)
    facts = crud.get_document_facts(db, document_id)
    return schemas.DocumentTextOut(document=document, pages=pages, facts=facts)


@router.post("/api/documents/{document_id}/process", response_model=schemas.DocumentOut)
def process_document(document_id: str, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File fisik tidak ditemukan di storage")
    return _process_document(db, document)


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    case_id = document.case_id
    filename = document.original_filename
    file_storage.delete_file(document.storage_path)
    db.delete(document)
    db.commit()
    crud.add_history(db, case_id, "DocumentDeleted", description=f"Dokumen '{filename}' dihapus")
    return None
