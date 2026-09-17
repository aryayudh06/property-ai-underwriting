"""
Klien untuk berkomunikasi dengan LLM Extraction Service (service terpisah, lihat
folder llm-service/). Main API TIDAK memanggil Ollama secara langsung dan TIDAK
memberi akses database utama ke LLM Extraction Service - komunikasi murni via HTTP API.
"""
import requests

from app.config import LLM_SERVICE_URL, LLM_SERVICE_TIMEOUT


class LLMServiceError(Exception):
    pass


def check_llm_service_health() -> dict:
    try:
        r = requests.get(f"{LLM_SERVICE_URL}/health", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"status": "unreachable", "error": str(e)}


def call_extract(payload: dict) -> dict:
    try:
        r = requests.post(f"{LLM_SERVICE_URL}/extract", json=payload, timeout=LLM_SERVICE_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        raise LLMServiceError(
            f"Gagal menghubungi LLM Extraction Service di {LLM_SERVICE_URL}. "
            f"Pastikan service tersebut berjalan (lihat folder llm-service/). Detail: {e}"
        )


def call_rag_answer(payload: dict) -> dict:
    """
    Panggil tahap generatif RAG di LLM Service (/rag/answer): mengirimkan
    query + context_chunks yang SUDAH di-retrieve secara lokal (lihat
    services/kb_service.py & services/rag_answer_service.py) untuk disuntikkan
    ke prompt Gemini (context injection) dan dijawab secara generatif.
    """
    try:
        r = requests.post(f"{LLM_SERVICE_URL}/rag/answer", json=payload, timeout=LLM_SERVICE_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        raise LLMServiceError(
            f"Gagal menghubungi LLM Extraction Service (/rag/answer) di {LLM_SERVICE_URL}. "
            f"Pastikan service tersebut berjalan (lihat folder llm-service/). Detail: {e}"
        )
