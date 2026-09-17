"""
RAG Knowledge Base service.

Menyediakan:
 - Ekstraksi teks dari dokumen KB (PDF/TXT) yang diupload underwriter
   (pedoman underwriting, SOP, risk appetite, manual risiko, ketentuan produk,
   template disposisi).
 - Chunking teks menjadi potongan-potongan kecil untuk diindeks.
 - Embedding lokal (feature hashing / bag-of-words vector) - dipakai sebagai
   pengganti embedding API pihak ketiga karena environment prototipe ini tidak
   memiliki akses ke API embedding cloud. Vektor tersimpan di SQLite
   (tabel knowledge_chunks.embedding_json) yang berperan sebagai "vector
   database" sederhana; pencarian dilakukan dengan cosine similarity.
 - Retrieval (pencarian) top-k chunk paling relevan terhadap sebuah query,
   lengkap dengan skor & sumber dokumen (judul, kategori) untuk ditampilkan
   sebagai referensi Knowledge Base.

CATATAN PENTING (guardrail RAG):
 Modul ini HANYA melakukan retrieval (pencarian potongan teks yang sudah ada
 di knowledge base). Ia TIDAK membuat/mengarang aturan baru. Pembentukan
 aturan/kondisi underwriting sepenuhnya menjadi tanggung jawab rule engine
 berbasis konfigurasi (lihat subject_to_engine.py) - hasil pencarian KB pada
 modul ini hanya dipakai sebagai *rujukan/sumber* pendukung, dan jika tidak ada
 potongan KB yang cukup relevan (skor di bawah ambang batas), sistem akan
 secara eksplisit menandainya "tidak ada rujukan KB yang relevan" alih-alih
 mengarang sumber.
"""
import hashlib
import math
import re
from pathlib import Path
from typing import List, Optional

from app.config import KB_CHUNK_SIZE, KB_CHUNK_OVERLAP, KB_EMBEDDING_DIM, KB_MIN_RELEVANCE_SCORE

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# Kata-kata umum Bahasa Indonesia/Inggris yang diabaikan agar embedding lebih
# fokus pada kata bermakna (stopword sederhana, bukan daftar lengkap NLP).
_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "atau",
    "ini", "itu", "adalah", "akan", "dapat", "harus", "tidak", "juga",
    "sebagai", "oleh", "dalam", "the", "and", "or", "is", "are", "to", "of",
    "a", "an", "in", "on", "for", "as", "be", "by",
}


# ---------------- Ekstraksi teks ----------------

def extract_text_from_file(file_path: str, file_format: str) -> str:
    """Ekstraksi teks mentah dari file KB (PDF/TXT/MD)."""
    fmt = file_format.lower().lstrip(".")
    if fmt == "pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        try:
            return "\n".join((page.get_text() or "") for page in doc)
        finally:
            doc.close()
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


# ---------------- Chunking ----------------

def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    chunk_size = chunk_size or KB_CHUNK_SIZE
    overlap = overlap or KB_CHUNK_OVERLAP
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


# ---------------- Embedding lokal (feature hashing) ----------------

def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall((text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def embed_text(text: str, dim: int = None) -> List[float]:
    """
    Embedding lokal deterministik berbasis feature hashing (hashing trick) +
    pembobotan term-frequency dengan peredaman log, lalu dinormalisasi (L2).
    Ini BUKAN model embedding neural (mis. Gemini/OpenAI embeddings) - dipakai
    sebagai implementasi "vector database" yang berfungsi penuh secara offline
    untuk keperluan prototipe. Setiap token diproyeksikan ke salah satu
    dimensi vektor menggunakan hash MD5, dengan tanda (+/-) juga ditentukan
    dari hash untuk mengurangi bias tabrakan (collision).
    """
    dim = dim or KB_EMBEDDING_DIM
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    term_counts = {}
    for t in tokens:
        term_counts[t] = term_counts.get(t, 0) + 1

    for term, count in term_counts.items():
        h = hashlib.md5(term.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % dim
        sign = 1.0 if int(h[8:9], 16) % 2 == 0 else -1.0
        weight = 1.0 + math.log(count)  # peredaman term-frequency
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------- Indexing & Search (dipanggil dari router, pakai db session) ----------------

def build_chunk_records(document_id: str, full_text: str) -> List[dict]:
    """Bangun daftar record chunk (siap disimpan ke tabel knowledge_chunks)."""
    chunks = chunk_text(full_text)
    records = []
    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        records.append({
            "document_id": document_id,
            "chunk_index": i,
            "text": chunk,
            "embedding": embedding,
            "char_count": len(chunk),
        })
    return records


def search_chunks(query: str, chunk_rows: list, top_k: int = 3, min_score: Optional[float] = None):
    """
    Cari top-k KnowledgeChunk (ORM rows, harus punya .embedding_json, .text,
    .document) paling relevan terhadap query berdasarkan cosine similarity.
    Mengembalikan list of dict {chunk, score} terurut skor menurun.
    Chunk dengan skor di bawah `min_score` TIDAK disertakan (agar sistem tidak
    memaksakan rujukan yang sebenarnya tidak relevan).
    """
    import json

    min_score = KB_MIN_RELEVANCE_SCORE if min_score is None else min_score
    query_vec = embed_text(query)
    scored = []
    for row in chunk_rows:
        try:
            emb = json.loads(row.embedding_json)
        except (TypeError, ValueError):
            continue
        score = cosine_similarity(query_vec, emb)
        if score >= min_score:
            scored.append({"chunk": row, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
