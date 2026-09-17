"""
Orkestrasi RAG generatif penuh: RETRIEVAL (lokal, embedding + vector search di
kb_service.py) → CONTEXT INJECTION → panggil LLM Service (/rag/answer) yang
memakai Gemini sebagai LLM generatif (dengan Ollama/mock sebagai fallback).

Main API tetap menjadi satu-satunya pihak yang memegang database Knowledge
Base (SQLite) - LLM Service tidak pernah mengakses database secara langsung,
hanya menerima potongan teks yang sudah dipilih lewat retrieval di sini.
"""
from sqlalchemy.orm import Session

from app import models
from app.services import kb_service, llm_client


def retrieve_context(db: Session, query: str, top_k: int = 5) -> list:
    """Tahap RETRIEVAL: cari potongan KB paling relevan secara lokal (embedding
    hashing + cosine similarity) - tidak melibatkan LLM sama sekali."""
    chunk_rows = db.query(models.KnowledgeChunk).all()
    results = kb_service.search_chunks(query, chunk_rows, top_k=top_k)
    context_chunks = []
    for r in results:
        chunk = r["chunk"]
        context_chunks.append({
            "document_title": chunk.document.title,
            "document_category": chunk.document.category.value,
            "text": chunk.text,
            "relevance_score": round(r["score"], 4),
        })
    return context_chunks


def ask(db: Session, query: str, top_k: int = 5, case_context: dict = None) -> dict:
    """
    Alur penuh: RETRIEVAL (lokal) → CONTEXT INJECTION → Gemini (via LLM
    Service /rag/answer). Mengembalikan jawaban beserta potongan konteks yang
    dipakai (untuk ditampilkan sebagai rujukan/transparansi ke underwriter).
    """
    context_chunks = retrieve_context(db, query, top_k=top_k)

    payload = {
        "query": query,
        "context_chunks": context_chunks,
        "case_context": case_context,
        "mode": "qa",
    }
    response = llm_client.call_rag_answer(payload)

    return {
        "query": query,
        "answer": response.get("answer", ""),
        "method": response.get("method"),
        "model": response.get("model"),
        "grounded": response.get("grounded", bool(context_chunks)),
        "warnings": response.get("warnings", []),
        "context_used": context_chunks,
    }


def narrate_subject_to(db: Session, subject_to: list, case_context: dict = None) -> dict:
    """
    Alur penuh untuk Disposisi: konteks yang disuntikkan (context injection)
    BUKAN hasil retrieval query bebas, melainkan gabungan teks kondisi Subject
    To/Conditions yang SUDAH ditentukan oleh rule engine beserta kutipan
    Knowledge Base yang sudah dirujuk masing-masing kondisi (subject_to_engine.py).
    Gemini hanya bertugas merangkai narasi yang enak dibaca - tidak menambah
    aturan baru (lihat instruksi grounding ketat di llm-service/app/rag_service.py).
    """
    context_chunks = []
    seen = set()
    condition_lines = []

    for cond in subject_to:
        condition_lines.append(f"- [{cond['category']}] {cond['text']}")
        ref = cond.get("kb_reference")
        if ref and ref["document_id"] not in seen:
            seen.add(ref["document_id"])
            context_chunks.append({
                "document_title": ref["document_title"],
                "document_category": ref["document_category"],
                "text": ref["excerpt"],
                "relevance_score": ref.get("relevance_score", 0.0),
            })

    query = (
        "Berikut adalah daftar kondisi Subject To/Conditions yang telah ditentukan oleh "
        "rule engine untuk sebuah risiko:\n" + "\n".join(condition_lines) +
        "\n\nSusun menjadi narasi ringkas (1-2 paragraf) yang enak dibaca oleh underwriter, "
        "mengelompokkan kondisi yang berkaitan, tanpa menambah syarat/ketentuan baru."
    )

    payload = {
        "query": query,
        "context_chunks": context_chunks,
        "case_context": case_context,
        "mode": "narrative",
    }
    response = llm_client.call_rag_answer(payload)

    return {
        "narrative": response.get("answer", ""),
        "method": response.get("method"),
        "model": response.get("model"),
        "grounded": response.get("grounded", bool(context_chunks)),
        "warnings": response.get("warnings", []),
        "context_used": context_chunks,
    }
