from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    CORS_ORIGINS,
    LLM_MODE,
    LLM_PROVIDER,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    GEMINI_MODEL,
)
from app.schemas import ExtractRequest, ExtractResponse, RagAnswerRequest, RagAnswerResponse
from app.ollama_client import is_ollama_available
from app.gemini_client import is_gemini_available
from app import extraction_service, rag_service

app = FastAPI(
    title="Property AI Underwriting - LLM Extraction Service",
    description="Service terpisah yang berkomunikasi dengan Ollama untuk mengekstrak "
                "data underwriting terstruktur dari teks dokumen. Tidak mengakses "
                "database utama secara langsung.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "llm-extraction-service",
        "llm_provider": LLM_PROVIDER,  # provider default saat mode="auto"
        "mode": LLM_MODE,
        "effective_mode": extraction_service.decide_mode(),  # "gemini" | "ollama" | "mock"
        "rag_effective_mode": rag_service.decide_mode(),
        "gemini": {
            "model": GEMINI_MODEL,
            "api_key_configured": is_gemini_available(),
        },
        "ollama": {
            # blueprint LLM lokal - lihat gemini_client.py & config.py
            # (LLM_PROVIDER=ollama) untuk beralih kembali ke sini
            "base_url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
            "available": is_ollama_available(),
        },
    }


@app.post("/extract", response_model=ExtractResponse)
def extract(payload: ExtractRequest):
    try:
        return extraction_service.run_extraction(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ekstraksi gagal: {e}")


@app.post("/rag/answer", response_model=RagAnswerResponse)
def rag_answer(payload: RagAnswerRequest):
    """
    Tahap generatif RAG: menerima query + context_chunks yang SUDAH di-retrieve
    oleh Main API (embedding lokal + vector search di kb_service.py), lalu
    menyuntikkan (context injection) potongan tersebut ke prompt dan meminta
    Gemini (atau Ollama/mock sebagai fallback) menyusun jawaban - digrounding
    ketat pada context_chunks yang diberikan.
    """
    try:
        return rag_service.answer(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG answer gagal: {e}")
