import json
import logging

from app.config import LLM_MODE, LLM_PROVIDER, OLLAMA_MODEL, GEMINI_MODEL
from app.field_definitions import FIELD_DEFINITIONS
from app.schemas import ExtractRequest, ExtractResponse, ExtractionResult
from app import ollama_client, gemini_client, mock_extractor

logger = logging.getLogger("extraction_service")

# Provider LLM "sungguhan" yang didukung, dan cara mengecek ketersediaannya
# masing-masing. Ollama dipertahankan sebagai blueprint LLM lokal di sini -
# menambah provider baru cukup dengan menambah entri baru di dict ini plus
# modul client-nya (lihat gemini_client.py / ollama_client.py sebagai contoh).
_AVAILABILITY_CHECKS = {
    "gemini": gemini_client.is_gemini_available,
    "ollama": ollama_client.is_ollama_available,
}

_PROVIDER_CLIENTS = {
    "gemini": (gemini_client.generate_json, gemini_client.GeminiError, GEMINI_MODEL),
    "ollama": (ollama_client.generate_json, ollama_client.OllamaError, OLLAMA_MODEL),
}


def decide_mode() -> str:
    if LLM_MODE == "mock":
        return "mock"
    if LLM_MODE in _PROVIDER_CLIENTS:
        # Paksa provider tertentu (mis. LLM_MODE=ollama atau LLM_MODE=gemini)
        return LLM_MODE
    # auto -> ikuti LLM_PROVIDER, fallback ke mock jika providernya belum siap
    provider = LLM_PROVIDER if LLM_PROVIDER in _PROVIDER_CLIENTS else "gemini"
    is_available = _AVAILABILITY_CHECKS[provider]
    return provider if is_available() else "mock"


def build_prompt(request: ExtractRequest) -> str:
    schema_lines = []
    for cat, fields in FIELD_DEFINITIONS.items():
        schema_lines.append(f'  "{cat}": {{')
        for field_key, desc in fields.items():
            schema_lines.append(
                f'    "{field_key}": {{"value": <isi atau "Not Found">, '
                f'"source_document": <nama file atau null>, "page": <nomor halaman atau null>, '
                f'"evidence": <kutipan singkat atau null>, "confidence": <0.0-1.0>}}  '
                f'// {desc}'
            )
        schema_lines.append("  },")
    schema_block = "\n".join(schema_lines)

    doc_blocks = []
    for doc in request.documents:
        for page in doc.pages:
            doc_blocks.append(
                f"--- Dokumen: {doc.filename} (tipe: {doc.doc_type}) | Halaman {page.page_number} ---\n"
                f"{page.text}\n"
            )
    combined_text = "\n".join(doc_blocks) if doc_blocks else "(tidak ada teks dokumen)"

    context_line = ""
    if request.case_context:
        context_line = (
            "Konteks case (dari sistem, hanya sebagai referensi, bukan sumber utama): "
            f"{json.dumps(request.case_context, ensure_ascii=False)}\n"
        )

    prompt = f"""Anda adalah asisten ekstraksi data underwriting properti untuk perusahaan asuransi.
Baca teks dokumen di bawah ini (hasil OCR/ekstraksi dari quotation slip, lembar analisa,
survey report, data aset, dsb) lalu isi data terstruktur sesuai skema JSON berikut.

ATURAN PENTING (WAJIB DIPATUHI):
1. Isi HANYA berdasarkan informasi yang benar-benar tertulis di teks dokumen. JANGAN mengarang,
   menebak, atau membuat asumsi apa pun.
2. Jika suatu informasi tidak ditemukan di teks, isi "value" dengan string "Not Found" dan
   "confidence" dengan 0.0.
3. Untuk setiap field yang berhasil diisi, sertakan "source_document" (nama file persis seperti
   di header dokumen) dan "page" (nomor halaman) tempat informasi tersebut ditemukan.
4. Sertakan "evidence" berupa kutipan singkat (maksimal 200 karakter) dari teks sumber yang
   mendukung nilai tersebut.
5. "confidence" bernilai 0.0 sampai 1.0 mencerminkan seberapa yakin Anda terhadap nilai tersebut.
6. Jika ada informasi yang saling bertentangan antar dokumen untuk field yang sama, catat di
   "conflicts" sebagai deskripsi singkat, dan pilih nilai yang paling dapat dipercaya (misalnya
   dari dokumen resmi seperti quotation slip / survey report).
7. Isi "data_gaps" dengan daftar "kategori.field" untuk semua field yang bernilai "Not Found".
8. Isi "sources" dengan daftar semua dokumen yang dirujuk: {{"document_id", "filename", "pages"}}.
9. "confidence" di level teratas adalah rata-rata keyakinan keseluruhan hasil ekstraksi.
10. KELUARKAN HANYA JSON VALID sesuai skema di bawah. JANGAN sertakan teks penjelasan, markdown,
    atau backtick apa pun di luar JSON.

{context_line}
Skema JSON yang harus diikuti persis (nama kategori dan field harus sama persis):
{{
{schema_block}
  "data_gaps": [ "kategori.field", ... ],
  "conflicts": [ "deskripsi konflik", ... ],
  "sources": [ {{"document_id": "...", "filename": "...", "pages": [1,2]}} ],
  "confidence": 0.0
}}

=== TEKS DOKUMEN ===
{combined_text}
=== AKHIR TEKS DOKUMEN ===

Kembalikan HANYA JSON sesuai skema di atas, tanpa teks tambahan apa pun.
"""
    return prompt


def _safe_get(d, key, default=None):
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def repair_result(raw: dict) -> ExtractionResult:
    """
    Pastikan seluruh kategori & field pada FIELD_DEFINITIONS selalu ada di hasil akhir.
    Field yang tidak dikembalikan oleh LLM/mock akan diisi "Not Found" dengan confidence 0.0
    (bukan diisi dengan asumsi), sesuai ketentuan produk.
    """
    if not isinstance(raw, dict):
        raw = {}

    complete = {}
    for cat, fields in FIELD_DEFINITIONS.items():
        cat_data = _safe_get(raw, cat, {}) or {}
        complete[cat] = {}
        for field_key in fields:
            fv = _safe_get(cat_data, field_key, None)
            value = _safe_get(fv, "value", None) if fv else None
            if value in (None, "", "null", "None"):
                complete[cat][field_key] = {
                    "value": "Not Found",
                    "source_document": _safe_get(fv, "source_document", None) if fv else None,
                    "page": _safe_get(fv, "page", None) if fv else None,
                    "evidence": _safe_get(fv, "evidence", None) if fv else None,
                    "confidence": 0.0,
                }
            else:
                complete[cat][field_key] = {
                    "value": value,
                    "source_document": _safe_get(fv, "source_document", None),
                    "page": _safe_get(fv, "page", None),
                    "evidence": _safe_get(fv, "evidence", None),
                    "confidence": _safe_get(fv, "confidence", 0.5),
                }

    data_gaps = raw.get("data_gaps") if isinstance(raw.get("data_gaps"), list) else []
    if not data_gaps:
        data_gaps = [
            f"{cat}.{field_key}"
            for cat, fields in complete.items()
            for field_key, fv in fields.items()
            if fv["value"] in (None, "Not Found", "")
        ]

    conflicts = raw.get("conflicts") if isinstance(raw.get("conflicts"), list) else []
    sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []

    confidences = [
        fv["confidence"] for fields in complete.values() for fv in fields.values()
        if isinstance(fv["confidence"], (int, float)) and fv["confidence"] > 0
    ]
    overall_confidence = raw.get("confidence")
    if not overall_confidence:
        overall_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    complete["data_gaps"] = data_gaps
    complete["conflicts"] = conflicts
    complete["sources"] = sources
    complete["confidence"] = overall_confidence

    # Validasi akhir & normalisasi tipe menggunakan Pydantic
    return ExtractionResult(**complete)


def run_extraction(request: ExtractRequest) -> ExtractResponse:
    warnings = []
    mode = decide_mode()

    if mode == "mock":
        raw = mock_extractor.build_mock_result(request.documents)
        result = repair_result(raw)
        return ExtractResponse(result=result, method="mock", model="mock-heuristic", warnings=warnings)

    # mode == "gemini" atau "ollama" - keduanya diperlakukan sama lewat
    # kontrak generate_json(prompt) -> str, hanya modul & exception class
    # yang berbeda per provider.
    generate_json, provider_error, model_name = _PROVIDER_CLIENTS[mode]

    prompt = build_prompt(request)
    try:
        raw_text = generate_json(prompt)
        raw = json.loads(raw_text)
    except provider_error as e:
        logger.warning("%s error, fallback ke mock: %s", mode, e)
        warnings.append(str(e))
        raw = mock_extractor.build_mock_result(request.documents)
        result = repair_result(raw)
        return ExtractResponse(result=result, method="mock_fallback", model=model_name, warnings=warnings)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Output %s bukan JSON valid, fallback ke mock: %s", mode, e)
        warnings.append(f"Output LLM ({mode}) bukan JSON valid, menggunakan mode mock sebagai fallback: {e}")
        raw = mock_extractor.build_mock_result(request.documents)
        result = repair_result(raw)
        return ExtractResponse(result=result, method="mock_fallback", model=model_name, warnings=warnings)

    result = repair_result(raw)
    return ExtractResponse(result=result, method=mode, model=model_name, warnings=warnings)
