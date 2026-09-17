"""
Klien untuk berkomunikasi dengan Gemini API (Google) sebagai provider LLM
default untuk ekstraksi data terstruktur.

Ditulis sejajar/kompatibel-antarmuka dengan ollama_client.py (yang tetap
dipertahankan apa adanya sebagai blueprint opsi LLM lokal - lihat
LLM_PROVIDER di config.py untuk beralih di antara "gemini" dan "ollama").
extraction_service.py memakai kedua modul ini secara bergantian lewat
fungsi generate_json(prompt) -> str, tanpa perlu tahu detail provider mana
yang sedang aktif.
"""
import os

import httpx
from google import genai
from google.genai import errors

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT

# Client di-cache (lazy-init) supaya tidak membuat instance baru di setiap
# request - genai.Client() murah untuk dibuat, tapi tetap lebih baik dipakai
# ulang (mengikuti rekomendasi umum SDK).
_client: genai.Client | None = None


class GeminiError(Exception):
    pass


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        # Jika GEMINI_API_KEY diisi di .env, pakai itu secara eksplisit.
        # Jika kosong, biarkan SDK mencoba auto-detect dari env
        # GEMINI_API_KEY / GOOGLE_API_KEY di level proses.
        _client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else genai.Client()
    return _client


def is_gemini_available() -> bool:
    """
    Cek kesiapan konfigurasi Gemini.

    Catatan: berbeda dengan is_ollama_available() (yang melakukan health-check
    HTTP nyata ke server lokal), di sini kita hanya memverifikasi API key
    sudah dikonfigurasi. Gemini adalah layanan cloud pihak ketiga berbayar,
    jadi kita sengaja menghindari memanggil API sungguhan hanya untuk cek
    ketersediaan (agar tidak memakan kuota/biaya di setiap health check /
    keputusan mode "auto").
    """
    return bool(GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY"))


def generate_json(prompt: str) -> str:
    """Kirim prompt ke Gemini API, minta output berupa JSON valid (mime_type
    application/json), setara dengan format="json" pada Ollama."""
    try:
        client = _get_client()
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=prompt,
            response_format={"type": "text", "mime_type": "application/json"},
            timeout=GEMINI_TIMEOUT,
        )
        return interaction.output_text or ""
    except (errors.APIError, httpx.HTTPError) as e:
        raise GeminiError(
            f"Gagal menghubungi Gemini API (model: {GEMINI_MODEL}): {e}"
        )
    except Exception as e:  # jaga-jaga utk error SDK/jaringan lain yang tak terduga
        raise GeminiError(
            f"Gagal menghubungi Gemini API (model: {GEMINI_MODEL}): {e}"
        )


def generate_text(prompt: str) -> str:
    """
    Sama seperti generate_json, tapi meminta keluaran teks bebas (bukan JSON) -
    dipakai untuk RAG generatif (retrieval → context injection → Gemini), mis.
    menjawab pertanyaan atau menyusun narasi berdasarkan potongan Knowledge Base
    yang sudah diambil lewat retrieval lokal (kb_service.py).
    """
    try:
        client = _get_client()
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=prompt,
            response_format={"type": "text", "mime_type": "text/plain"},
            timeout=GEMINI_TIMEOUT,
        )
        return interaction.output_text or ""
    except (errors.APIError, httpx.HTTPError) as e:
        raise GeminiError(
            f"Gagal menghubungi Gemini API (model: {GEMINI_MODEL}): {e}"
        )
    except Exception as e:
        raise GeminiError(
            f"Gagal menghubungi Gemini API (model: {GEMINI_MODEL}): {e}"
        )
