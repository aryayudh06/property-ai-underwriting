"""Klien HTTP sederhana untuk berkomunikasi dengan server Ollama."""
import requests

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


class OllamaError(Exception):
    pass


def is_ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def generate_json(prompt: str) -> str:
    """Kirim prompt ke Ollama dengan format=json agar output berupa JSON valid."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")
    except requests.exceptions.RequestException as e:
        raise OllamaError(
            f"Gagal menghubungi Ollama di {OLLAMA_BASE_URL} (model: {OLLAMA_MODEL}): {e}"
        )


def generate_text(prompt: str) -> str:
    """Sama seperti generate_json, tapi tanpa memaksa format JSON - dipakai
    untuk RAG generatif (jawaban naratif berbasis konteks yang di-retrieve)."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")
    except requests.exceptions.RequestException as e:
        raise OllamaError(
            f"Gagal menghubungi Ollama di {OLLAMA_BASE_URL} (model: {OLLAMA_MODEL}): {e}"
        )
