import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session

from app import models
from app.config import KB_STORAGE_DIR, KB_ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE
from app.database import get_db
from app.services import kb_service, rag_answer_service

router = APIRouter(tags=["RAG Knowledge Base"])

VALID_CATEGORIES = [c.value for c in models.KnowledgeCategory]


def _doc_out(doc: models.KnowledgeDocument) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category.value if hasattr(doc.category, "value") else str(doc.category),
        "original_filename": doc.original_filename,
        "file_format": doc.file_format,
        "chunk_count": doc.chunk_count,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "preview": (doc.full_text or "")[:400],
    }


@router.get("/api/knowledge/categories")
def list_categories():
    return {"categories": VALID_CATEGORIES}


@router.get("/api/knowledge")
def list_knowledge_documents(db: Session = Depends(get_db)):
    """Daftar dokumen Knowledge Base yang sudah diindeks (pedoman underwriting, SOP, dst)."""
    docs = db.query(models.KnowledgeDocument).order_by(models.KnowledgeDocument.uploaded_at.desc()).all()
    return [_doc_out(d) for d in docs]


@router.post("/api/knowledge/upload")
async def upload_knowledge_document(
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(None),
    text_content: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload & indeks dokumen pengetahuan (pedoman underwriting, SOP, risk
    appetite, manual risiko, ketentuan produk, template disposisi).
    Mendukung upload file (PDF/TXT/MD) ATAU input teks langsung (text_content)
    untuk kebutuhan demo/testing cepat tanpa file.
    """
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Kategori tidak valid. Pilihan: {VALID_CATEGORIES}")

    if not file and not text_content:
        raise HTTPException(status_code=400, detail="Harus menyertakan file ATAU text_content.")

    original_filename = None
    file_format = "txt"
    full_text = ""

    if file:
        ext = Path(file.filename).suffix.lower()
        if ext not in KB_ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format file '{ext}' tidak didukung untuk Knowledge Base. Gunakan PDF/TXT/MD.",
            )
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="Ukuran file melebihi batas maksimum.")

        stored_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = KB_STORAGE_DIR / stored_name
        with open(dest_path, "wb") as f:
            f.write(raw)

        original_filename = file.filename
        file_format = ext.lstrip(".")
        try:
            full_text = kb_service.extract_text_from_file(str(dest_path), file_format)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gagal mengekstrak teks dari file: {e}")
    else:
        full_text = text_content
        file_format = "txt"

    if not full_text or not full_text.strip():
        raise HTTPException(status_code=400, detail="Dokumen tidak memiliki teks yang dapat diindeks.")

    doc = models.KnowledgeDocument(
        title=title,
        category=category,
        original_filename=original_filename,
        file_format=file_format,
        full_text=full_text,
        chunk_count=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Chunking + embedding (indexing ke "vector database")
    chunk_records = kb_service.build_chunk_records(doc.id, full_text)
    for rec in chunk_records:
        db.add(models.KnowledgeChunk(
            document_id=rec["document_id"],
            chunk_index=rec["chunk_index"],
            text=rec["text"],
            embedding_json=json.dumps(rec["embedding"]),
            char_count=rec["char_count"],
        ))
    doc.chunk_count = len(chunk_records)
    db.commit()
    db.refresh(doc)

    return _doc_out(doc)


@router.get("/api/knowledge/{doc_id}")
def get_knowledge_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen Knowledge Base tidak ditemukan")
    out = _doc_out(doc)
    out["chunks"] = [
        {"chunk_index": c.chunk_index, "text": c.text, "char_count": c.char_count}
        for c in sorted(doc.chunks, key=lambda x: x.chunk_index)
    ]
    return out


@router.delete("/api/knowledge/{doc_id}")
def delete_knowledge_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(models.KnowledgeDocument).filter(models.KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen Knowledge Base tidak ditemukan")
    db.delete(doc)
    db.commit()
    return {"deleted": True, "id": doc_id}


@router.post("/api/knowledge/search")
def search_knowledge(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    Pencarian RAG: cari potongan (chunk) Knowledge Base paling relevan
    terhadap sebuah query, lengkap dengan skor similarity & dokumen sumber -
    untuk ditampilkan sebagai referensi yang dipakai (retrieval saja, tidak
    men-generate teks baru).
    """
    query = (payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 5))
    if not query:
        raise HTTPException(status_code=400, detail="Field 'query' wajib diisi.")

    chunk_rows = db.query(models.KnowledgeChunk).all()
    results = kb_service.search_chunks(query, chunk_rows, top_k=top_k)

    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "document_id": r["chunk"].document.id,
                "document_title": r["chunk"].document.title,
                "document_category": r["chunk"].document.category.value,
                "chunk_index": r["chunk"].chunk_index,
                "text": r["chunk"].text,
                "relevance_score": round(r["score"], 4),
            }
            for r in results
        ],
    }


@router.post("/api/knowledge/ask")
def ask_knowledge(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    RAG generatif penuh: RETRIEVAL (embedding lokal + vector search, lihat
    kb_service.py) → CONTEXT INJECTION (potongan hasil retrieval disuntikkan
    ke prompt) → GEMINI (dipanggil lewat LLM Service /rag/answer, dengan
    Ollama/mock sebagai fallback bila Gemini tidak tersedia).

    Berbeda dari /api/knowledge/search (yang hanya retrieval), endpoint ini
    menghasilkan jawaban naratif dari LLM - namun digrounding ketat pada
    potongan Knowledge Base yang di-retrieve; jika tidak ada potongan yang
    cukup relevan, LLM diinstruksikan untuk mengatakan demikian, bukan
    mengarang jawaban dari pengetahuan umum.
    """
    query = (payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 5))
    if not query:
        raise HTTPException(status_code=400, detail="Field 'query' wajib diisi.")

    try:
        result = rag_answer_service.ask(db, query, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal memproses RAG answer: {e}")

    return result
