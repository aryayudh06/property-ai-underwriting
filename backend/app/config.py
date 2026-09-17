"""
Konfigurasi aplikasi - dibaca dari environment variables (.env) dengan nilai default.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend

# Muat variabel dari file .env di root folder backend/ (jika ada).
# Tanpa ini, isi .env TIDAK akan pernah terbaca oleh os.getenv().
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Direktori penyimpanan file upload (lokal)
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage" / "uploads"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Database SQLite
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'storage' / 'underwriting.db'}")

# Batas ukuran file upload (bytes) - default 25 MB
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 25 * 1024 * 1024))

# Ekstensi file yang diizinkan
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Path ke binary tesseract (opsional, jika tidak ada di PATH).
# Dibersihkan dari spasi/kutip yang tidak sengaja ikut ter-copy dari file .env.
_raw_tesseract_cmd = os.getenv("TESSERACT_CMD", "")
TESSERACT_CMD = _raw_tesseract_cmd.strip().strip('"').strip("'") or None

# Ambang batas jumlah karakter -- di bawah ini dianggap "tidak memadai" & perlu OCR
MIN_TEXT_LENGTH_THRESHOLD = int(os.getenv("MIN_TEXT_LENGTH_THRESHOLD", 20))

# Alamat LLM Extraction Service (service terpisah, lihat folder llm-service/)
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8001")
LLM_SERVICE_TIMEOUT = int(os.getenv("LLM_SERVICE_TIMEOUT", 200))

# Frontend static directory
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", BASE_DIR.parent / "frontend"))

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Direktori penyimpanan file dokumen Knowledge Base (RAG) - terpisah dari upload dokumen case
KB_STORAGE_DIR = Path(os.getenv("KB_STORAGE_DIR", BASE_DIR / "storage" / "knowledge_base"))
KB_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Ekstensi file yang didukung untuk upload Knowledge Base
KB_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

# Ukuran chunk teks (karakter) untuk indexing RAG + overlap antar-chunk.
# Dibuat relatif kecil agar tiap chunk lebih fokus per-topik (meningkatkan presisi
# retrieval), karena satu paragraf pedoman/SOP sering membahas beberapa topik sekaligus.
KB_CHUNK_SIZE = int(os.getenv("KB_CHUNK_SIZE", 420))
KB_CHUNK_OVERLAP = int(os.getenv("KB_CHUNK_OVERLAP", 80))

# Dimensi vektor embedding lokal (hashing-based, lihat services/kb_service.py)
KB_EMBEDDING_DIM = int(os.getenv("KB_EMBEDDING_DIM", 256))

# Ambang batas skor cosine similarity minimum agar sebuah chunk KB dianggap
# "relevan" dan dapat dijadikan rujukan/sumber pada rule engine & pencarian RAG.
KB_MIN_RELEVANCE_SCORE = float(os.getenv("KB_MIN_RELEVANCE_SCORE", 0.10))
