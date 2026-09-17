import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # .../llm-service

# Muat variabel dari file .env di root folder llm-service/ (jika ada).
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Provider LLM aktif saat LLM_MODE="auto": "gemini" (default, cloud) atau
# "ollama" (LLM lokal - dipertahankan sebagai blueprint, lihat bagian
# OLLAMA_* di bawah). Untuk kembali memakai Ollama sepenuhnya seperti
# sebelumnya, set LLM_PROVIDER=ollama (atau paksa via LLM_MODE=ollama).
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# --- Konfigurasi Gemini API (provider default) ---------------------------
# API key Gemini (buat di https://aistudio.google.com/apikey). Jika kosong,
# SDK google-genai otomatis mencoba membaca env GEMINI_API_KEY/GOOGLE_API_KEY
# di level proses - variabel ini hanya cara eksplisit untuk mengisinya lewat
# file .env service ini.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model Gemini yang dipakai. Cek daftar model & alias terbaru di
# https://ai.google.dev/gemini-api/docs/models - hindari alias "-latest"
# untuk pemakaian yang butuh stabilitas karena mengarah ke model eksperimental.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Timeout request ke Gemini API (detik)
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", 120))

# --- Konfigurasi Ollama (blueprint LLM lokal - opsional) ------------------
# Alamat server Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Model Ollama yang digunakan (harus sudah di-pull, mis. `ollama pull llama3.1`)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Timeout request ke Ollama (detik) - model besar bisa butuh waktu lama
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", 180))

# Mode operasi: "auto" (pakai provider di LLM_PROVIDER jika tersedia, else
# mock), "gemini" (paksa pakai Gemini, fallback mock+warning jika gagal),
# "ollama" (paksa pakai Ollama, fallback mock+warning jika gagal/tidak
# tersedia), "mock" (selalu pakai mode mock, untuk demo tanpa LLM sama sekali)
LLM_MODE = os.getenv("LLM_MODE", "auto").lower()

PORT = int(os.getenv("PORT", 8001))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
