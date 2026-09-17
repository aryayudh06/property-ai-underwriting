"""
Tahap generatif RAG: context injection + pemanggilan LLM (Gemini, dengan
Ollama & mock sebagai fallback/blueprint), MENYUSUL tahap retrieval yang
sudah dilakukan di Main API (embedding lokal + vector search, lihat
backend/app/services/kb_service.py).

Alur lengkap "retrieval → context injection → Gemini":
  1. RETRIEVAL   : Main API mencari potongan (chunk) Knowledge Base paling
                   relevan via embedding lokal + cosine similarity
                   (backend/app/services/kb_service.py) - tidak melibatkan LLM.
  2. CONTEXT      : Potongan hasil retrieval tsb dikirim sebagai
     INJECTION      `context_chunks` ke endpoint /rag/answer service ini.
  3. GENERATIF    : Modul ini menyusun prompt yang menyuntikkan context_chunks
                   apa adanya ke dalam instruksi, lalu memanggil Gemini
                   (atau Ollama/mock) untuk menghasilkan jawaban akhir -
                   dengan aturan tegas: HANYA boleh menjawab berdasarkan
                   konteks yang diberikan, dan WAJIB mengatakan jika informasi
                   tidak tersedia di konteks (tidak boleh mengarang aturan).
"""
import logging

from app.config import LLM_MODE, LLM_PROVIDER, OLLAMA_MODEL, GEMINI_MODEL
from app.schemas import RagAnswerRequest, RagAnswerResponse
from app import ollama_client, gemini_client

logger = logging.getLogger("rag_service")

_TEXT_PROVIDER_CLIENTS = {
    "gemini": (gemini_client.generate_text, gemini_client.GeminiError, GEMINI_MODEL),
    "ollama": (ollama_client.generate_text, ollama_client.OllamaError, OLLAMA_MODEL),
}

_AVAILABILITY_CHECKS = {
    "gemini": gemini_client.is_gemini_available,
    "ollama": ollama_client.is_ollama_available,
}


def decide_mode() -> str:
    if LLM_MODE == "mock":
        return "mock"
    if LLM_MODE in _TEXT_PROVIDER_CLIENTS:
        return LLM_MODE
    provider = LLM_PROVIDER if LLM_PROVIDER in _TEXT_PROVIDER_CLIENTS else "gemini"
    is_available = _AVAILABILITY_CHECKS[provider]
    return provider if is_available() else "mock"


def build_prompt(request: RagAnswerRequest) -> str:
    if not request.context_chunks:
        context_block = "(TIDAK ADA POTONGAN KNOWLEDGE BASE YANG RELEVAN DITEMUKAN)"
    else:
        parts = []
        for i, c in enumerate(request.context_chunks, start=1):
            parts.append(
                f"[Sumber {i}] Dokumen: \"{c.document_title}\" (Kategori: {c.document_category}, "
                f"skor relevansi: {c.relevance_score})\n{c.text}"
            )
        context_block = "\n\n".join(parts)

    case_line = ""
    if request.case_context:
        case_line = f"Konteks case (referensi saja, bukan sumber aturan): {request.case_context}\n"

    if request.mode == "narrative":
        task_instruction = (
            "TUGAS: Susun narasi/ringkasan yang mengalir dan mudah dibaca underwriter, "
            "berdasarkan daftar kondisi Subject To/Conditions yang sudah ditentukan oleh "
            "rule engine (dikirim sebagai bagian dari PERTANYAAN di bawah), dengan "
            "memperkaya penjelasan HANYA menggunakan kalimat dari POTONGAN KNOWLEDGE BASE "
            "di bawah. JANGAN menambahkan syarat/ketentuan/angka baru yang tidak ada pada "
            "kondisi atau konteks yang diberikan - tugas Anda murni merangkai kalimat "
            "menjadi narasi yang enak dibaca, bukan membuat aturan baru."
        )
    else:
        task_instruction = (
            "TUGAS: Jawab PERTANYAAN underwriter di bawah, HANYA berdasarkan isi "
            "POTONGAN KNOWLEDGE BASE yang diberikan."
        )

    prompt = f"""Anda adalah asisten underwriting yang membantu menjawab pertanyaan HANYA
berdasarkan potongan dokumen Knowledge Base (pedoman underwriting, SOP, risk appetite,
manual risiko, ketentuan produk, template disposisi) yang disediakan di bawah ini.

ATURAN PENTING (WAJIB DIPATUHI, TIDAK BOLEH DILANGGAR):
1. HANYA gunakan informasi yang benar-benar ada di POTONGAN KNOWLEDGE BASE di bawah.
   JANGAN mengarang, menebak, atau menambahkan aturan/syarat/angka yang tidak tertulis
   di sana, walaupun menurut Anda masuk akal secara umum.
2. Jika POTONGAN KNOWLEDGE BASE di bawah kosong atau tidak cukup relevan untuk menjawab,
   katakan dengan jelas: "Tidak ditemukan informasi yang relevan pada Knowledge Base
   untuk menjawab pertanyaan ini." JANGAN memaksakan jawaban dari pengetahuan umum Anda.
3. Setiap pernyataan yang Anda buat harus dapat ditelusuri ke salah satu [Sumber N] di
   bawah. Di akhir jawaban, sertakan baris "Sumber: " diikuti daftar judul dokumen yang
   benar-benar Anda pakai.
4. Jawaban singkat, jelas, dan dalam Bahasa Indonesia formal.

{task_instruction}

{case_line}
=== POTONGAN KNOWLEDGE BASE (HASIL RETRIEVAL) ===
{context_block}
=== AKHIR POTONGAN KNOWLEDGE BASE ===

PERTANYAAN:
{request.query}

Jawaban Anda:
"""
    return prompt


def _mock_answer(request: RagAnswerRequest) -> str:
    """
    Fallback ekstraktif (tanpa LLM) - dipakai jika tidak ada provider LLM yang
    aktif/berhasil. Murni menyusun ulang (bukan generatif bebas) potongan
    konteks yang paling relevan sehingga tetap 100% grounded pada retrieval,
    hanya saja tanpa kefasihan bahasa dari model generatif.
    """
    if not request.context_chunks:
        return (
            "Tidak ditemukan informasi yang relevan pada Knowledge Base untuk "
            "menjawab pertanyaan ini."
        )
    lines = ["Ringkasan berdasarkan potongan Knowledge Base yang paling relevan (mode mock, tanpa LLM generatif):"]
    used_titles = []
    for c in request.context_chunks:
        lines.append(f"- {c.text}")
        if c.document_title not in used_titles:
            used_titles.append(c.document_title)
    lines.append("")
    lines.append("Sumber: " + ", ".join(used_titles))
    return "\n".join(lines)


def answer(request: RagAnswerRequest) -> RagAnswerResponse:
    warnings = []
    mode = decide_mode()
    grounded = bool(request.context_chunks)

    if mode == "mock":
        return RagAnswerResponse(
            answer=_mock_answer(request), method="mock", model="mock-extractive",
            grounded=grounded, warnings=warnings,
        )

    generate_text, provider_error, model_name = _TEXT_PROVIDER_CLIENTS[mode]
    prompt = build_prompt(request)
    try:
        text = generate_text(prompt)
        if not text or not text.strip():
            raise ValueError("Model mengembalikan jawaban kosong")
        return RagAnswerResponse(
            answer=text.strip(), method=mode, model=model_name, grounded=grounded, warnings=warnings,
        )
    except provider_error as e:
        logger.warning("%s error pada RAG answer, fallback ke mock: %s", mode, e)
        warnings.append(str(e))
        return RagAnswerResponse(
            answer=_mock_answer(request), method="mock_fallback", model=model_name,
            grounded=grounded, warnings=warnings,
        )
    except Exception as e:
        logger.warning("Error tak terduga pada RAG answer, fallback ke mock: %s", e)
        warnings.append(str(e))
        return RagAnswerResponse(
            answer=_mock_answer(request), method="mock_fallback", model=model_name,
            grounded=grounded, warnings=warnings,
        )
