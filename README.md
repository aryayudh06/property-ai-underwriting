# Property AI Underwriting Assistant — Prototype

Prototype fungsional untuk tiga modul:

1. **Case Management** — CRUD case underwriting, manajemen status (Draft → Processing → Reviewed → Completed), dan histori aktivitas.
2. **Document Processing** — upload multi-dokumen (PDF/JPG/PNG) per case, ekstraksi teks (PyMuPDF), fallback OCR (Tesseract) untuk PDF hasil scan/gambar, klasifikasi jenis dokumen, dan penyimpanan fakta/kutipan yang dapat ditelusuri ke dokumen & halaman sumbernya.
3. **Structured Data Extraction** — menggunakan LLM (**Gemini API** secara default, dengan **Ollama lokal dipertahankan sebagai blueprint**, via service terpisah) untuk membaca teks hasil OCR/ekstraksi seluruh dokumen pada sebuah case, lalu mengisi form data underwriting terstruktur (tertanggung, bangunan, aset, proteksi kebakaran, risiko bencana alam, riwayat klaim, coverage, hasil survey, dst) yang dapat diperiksa & diedit oleh underwriter, lengkap dengan evidence, sumber dokumen/halaman, dan confidence. Dilengkapi **Mock Rule Engine** sederhana berbasis konfigurasi JSON untuk memberi sinyal awal risk level.

> **Catatan:** Modul 1 & 2 **tidak** menggunakan LLM/AI generatif sama sekali (klasifikasi dokumen berbasis keyword matching). Modul 3 menggunakan LLM (**Gemini API** secara default, dengan **Ollama lokal dipertahankan sebagai blueprint/opsi alternatif**) **hanya** untuk ekstraksi data terstruktur dari teks yang sudah ada — **bukan** RAG, bukan rules engine analisa underwriting yang sesungguhnya, dan bukan analisa/rekomendasi keputusan underwriting. Mock Rule Engine bersifat ilustratif berbasis kondisi sederhana.

## Arsitektur Layanan

```
┌─────────────────────────┐      HTTP       ┌───────────────────────────┐
│ Frontend + Main FastAPI │ ───────────────▶│  LLM Extraction Service   │
│   (port 8000)           │◀─────────────────│      (port 8001)          │
│   - Case Management     │   JSON hasil     │  - Terima teks dokumen    │
│   - Document Processing │   ekstraksi      │  - Bangun prompt          │
│   - SQLite (semua data) │                  │  - Validasi output        │
│   - Mock Rule Engine    │                  │    dgn Pydantic           │
└─────────────────────────┘                  │  - Mode mock jika LLM     │
                                              │    tidak tersedia         │
                                              └─────────────┬─────────────┘
                                                             │
                                     provider aktif dipilih via LLM_PROVIDER
                                                             │
                                        ┌────────────────────┴────────────────────┐
                                        ▼                                         ▼
                          ┌──────────────────────────┐          ┌──────────────────────────┐
                          │   Gemini API (default)    │          │  Ollama (blueprint lokal) │
                          │   cloud, generativelanguage│         │  http://localhost:11434  │
                          │   .googleapis.com          │          │  (opsional, dijalankan    │
                          └──────────────────────────┘           │   sendiri via ollama serve)│
                                                                  └──────────────────────────┘
```

- **Main API (8000)** menyimpan seluruh data (case, dokumen, hasil ekstraksi, hasil mock rules) di SQLite. Main API **tidak** memanggil LLM manapun secara langsung — selalu lewat LLM Extraction Service.
- **LLM Extraction Service (8001)** adalah service Python/FastAPI **terpisah**, stateless, **tidak punya akses ke database utama**. Ia hanya menerima teks dokumen via HTTP dari Main API, memanggil provider LLM yang aktif, memvalidasi hasilnya dengan Pydantic, lalu mengembalikan JSON terstruktur ke Main API.
- **Provider LLM dapat dipilih lewat `LLM_PROVIDER`** di `llm-service/.env` (lihat tabel konfigurasi di bawah):
  - **`gemini` (default)** — memanggil Gemini API (`google-genai` SDK) memakai `GEMINI_API_KEY`. Tidak perlu server lokal apa pun.
  - **`ollama`** — kode & alur kerja Ollama versi sebelumnya **dipertahankan utuh sebagai blueprint** (`app/ollama_client.py`) untuk yang ingin tetap memakai LLM lokal/offline. Set `LLM_PROVIDER=ollama` (atau `LLM_MODE=ollama` untuk memaksa) untuk kembali 100% ke setup lama — jalankan `ollama serve` seperti sebelumnya.
- Jika provider yang aktif tidak tersedia/gagal/timeout, LLM Extraction Service otomatis **fallback ke mode mock** (heuristik keyword sederhana) sehingga prototype tetap bisa didemokan end-to-end tanpa LLM/API key sama sekali.

---

## Struktur Folder

```
property-ai-underwriting/
├── backend/                        # Main API (port 8000)
│   ├── app/
│   │   ├── main.py                 # Entry point FastAPI
│   │   ├── config.py               # Konfigurasi (env vars)
│   │   ├── database.py             # Setup SQLAlchemy + SQLite
│   │   ├── models.py               # ORM: Case, Document, DocumentPage, ExtractedFact,
│   │   │                           #      CaseHistory, ExtractionVersion, MockRulesResult
│   │   ├── schemas.py               # Pydantic schemas Case/Document
│   │   ├── crud.py                  # Operasi database
│   │   ├── seed.py                  # Data dummy untuk pengujian
│   │   ├── rules_config.json        # Konfigurasi Mock Rule Engine (JSON, bukan kode)
│   │   ├── routers/
│   │   │   ├── cases.py             # Endpoint Case Management
│   │   │   ├── documents.py         # Endpoint Document Processing
│   │   │   ├── extraction.py        # Endpoint Structured Data Extraction + Mock Rules
│   │   │   └── health.py
│   │   └── services/
│   │       ├── file_storage.py          # Simpan file upload ke disk lokal
│   │       ├── document_processor.py    # Ekstraksi teks + klasifikasi dokumen
│   │       ├── ocr_service.py           # OCR via Tesseract
│   │       ├── llm_client.py            # Klien HTTP ke LLM Extraction Service
│   │       └── mock_rules_engine.py     # Evaluasi rules_config.json
│   ├── storage/
│   │   ├── uploads/                 # File dokumen tersimpan di sini (per case)
│   │   └── underwriting.db          # Database SQLite (dibuat otomatis)
│   ├── requirements.txt
│   └── .env.example
├── llm-service/                    # LLM Extraction Service (port 8001) - service terpisah
│   ├── app/
│   │   ├── main.py                  # Entry point FastAPI (/health, /extract)
│   │   ├── config.py                # LLM_PROVIDER, GEMINI_*, OLLAMA_*, LLM_MODE, dst
│   │   ├── field_definitions.py      # Skema kategori & field underwriting (single source of truth)
│   │   ├── schemas.py                # Pydantic: FieldValue, ExtractionResult, request/response
│   │   ├── gemini_client.py          # Klien Gemini API (provider default) via SDK google-genai
│   │   ├── ollama_client.py          # Klien HTTP ke Ollama (blueprint LLM lokal, opsional)
│   │   ├── mock_extractor.py         # Heuristik fallback jika provider LLM aktif tidak tersedia
│   │   └── extraction_service.py     # Prompt builder + orkestrasi antar-provider + repair/validasi hasil
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js             # Wrapper fetch ke REST API (Main API)
│       ├── cases.js           # Logika UI Case Management
│       ├── documents.js       # Logika UI Document Processing
│       ├── extraction.js      # Logika UI Structured Data Extraction + Mock Rules
│       └── app.js             # Bootstrap, navigasi, modal, toast
├── run.sh                     # Menjalankan Main API + Frontend
├── run_llm_service.sh         # Menjalankan LLM Extraction Service
└── README.md
```

---

## Prasyarat

- **Python 3.11+**
- **Tesseract OCR** terpasang di sistem (untuk fitur OCR gambar/PDF hasil scan)
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-ind`
  - macOS (Homebrew): `brew install tesseract tesseract-lang`
  - Windows: unduh installer dari https://github.com/UB-Mannheim/tesseract/wiki, lalu set `TESSERACT_CMD` di file `.env` menuju `tesseract.exe`
  - Jika Tesseract tidak terpasang, aplikasi tetap berjalan normal — hanya fitur OCR yang tidak akan berfungsi (status akan `Failed` untuk dokumen yang butuh OCR, dan indikator "OCR" di header UI akan menampilkan status tidak aktif).
- **Gemini API key** (opsional, hanya untuk modul Structured Data Extraction dengan LLM sungguhan — provider default)
  - Buat API key gratis di https://aistudio.google.com/apikey
  - Isi `GEMINI_API_KEY=...` di `llm-service/.env`
  - **Jika `GEMINI_API_KEY` tidak diisi, modul Structured Data Extraction tetap berfungsi** dalam **mode mock** (heuristik sederhana) — cukup jalankan LLM Extraction Service seperti biasa, ia akan otomatis fallback ke mock.
- **Ollama** (opsional — blueprint LLM lokal/offline, alternatif dari Gemini API)
  - Unduh & install dari https://ollama.com
  - Jalankan `ollama serve` (biasanya otomatis berjalan sebagai service setelah install)
  - Pull model yang ingin dipakai, contoh: `ollama pull llama3.1`
  - Untuk memakainya, set `LLM_PROVIDER=ollama` di `llm-service/.env` (lihat bagian Konfigurasi)
- **Koneksi internet dari server Main API** (opsional, hanya untuk fitur **Analisis Risiko Bencana Wilayah** — lihat bagian [Analisis Kualitatif & Risiko Bencana Wilayah](#analisis-kualitatif--risiko-bencana-wilayah)). Fitur ini melakukan web scraping ke `news.google.com`; tanpa akses internet, fitur lain pada aplikasi tetap berjalan normal, hanya hasil analisis ini yang akan kosong disertai `warning`.

---

## Cara Menjalankan (Linux/Mac)

Jalankan di **2 terminal terpisah** (LLM Extraction Service opsional jika hanya ingin uji Case Management/Document Processing):

**Terminal 1 - Main API + Frontend (wajib):**
```bash
git clone <repo-ini>   # atau ekstrak folder proyek
cd property-ai-underwriting
chmod +x run.sh run_llm_service.sh
./run.sh
```

**Terminal 2 - LLM Extraction Service (untuk modul Structured Data Extraction):**
```bash
cd property-ai-underwriting
cp llm-service/.env.example llm-service/.env   # lalu isi GEMINI_API_KEY di dalamnya
./run_llm_service.sh
```
Dengan `GEMINI_API_KEY` terisi, ekstraksi memakai Gemini API secara langsung — **tidak perlu terminal/service tambahan**. Tanpa API key, service otomatis jalan dalam mode mock.

**Terminal 3 - Ollama (opsional, hanya jika ingin beralih ke blueprint LLM lokal alih-alih Gemini):**
```bash
# Set LLM_PROVIDER=ollama di llm-service/.env terlebih dahulu, lalu:
ollama serve
```

`run.sh` akan otomatis:
1. Membuat virtual environment (`backend/.venv`)
2. Menginstall dependencies dari `requirements.txt`
3. Menyalin `.env.example` → `.env` (jika belum ada)
4. Menjalankan Main API di `http://localhost:8000`

`run_llm_service.sh` melakukan hal yang sama untuk `llm-service/`, menjalankan di `http://localhost:8001`.

Buka browser ke **http://localhost:8000** — frontend (HTML/CSS/JS) langsung ter-serve oleh FastAPI di root path yang sama dengan API.

> Jika Anda hanya membuka Terminal 1 (tanpa menjalankan LLM Extraction Service), fitur Case Management, Document Processing, Upload, dan OCR tetap berjalan normal seperti biasa — hanya tombol **"Extract Structured Data"** yang akan menampilkan pesan error karena service di port 8001 belum aktif.

## Cara Menjalankan (Windows / manual, semua OS)

**Main API:**
```bash
cd property-ai-underwriting/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/Mac

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**LLM Extraction Service (terminal terpisah):**
```bash
cd property-ai-underwriting/llm-service
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/Mac

uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Lalu buka **http://localhost:8000**.

Saat pertama kali dijalankan, database SQLite (`backend/storage/underwriting.db`) akan dibuat otomatis beserta **4 case dummy** untuk pengujian.

---

## Troubleshooting Instalasi

**Error saat instalasi PyMuPDF: `Preparing metadata (pyproject.toml) did not run successfully`**

Ini terjadi jika pip versi lama mencoba build PyMuPDF dari source karena tidak menemukan wheel prebuilt untuk versi Python yang dipakai (sering terjadi di Python versi sangat baru, mis. 3.13, dengan pip lama). Solusi:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Jika masih gagal, gunakan Python 3.11 atau 3.12 (paling banyak didukung wheel-nya), atau install PyMuPDF secara terpisah dengan versi terbaru: `pip install --upgrade PyMuPDF`.

## Dokumentasi API Interaktif

FastAPI otomatis menyediakan dokumentasi di:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Daftar Endpoint API

### Case Management
| Method | Endpoint | Keterangan |
|---|---|---|
| POST | `/api/cases` | Buat case baru |
| GET | `/api/cases?status=&search=` | Daftar case (filter status/pencarian) |
| GET | `/api/cases/{case_id}` | Detail case + daftar dokumen |
| PUT | `/api/cases/{case_id}` | Ubah data case |
| PATCH | `/api/cases/{case_id}/status` | Ubah status case saja |
| DELETE | `/api/cases/{case_id}` | Hapus case (cascade ke dokumen & histori) |
| GET | `/api/cases/{case_id}/history` | Histori aktivitas case |

### Document Processing
| Method | Endpoint | Keterangan |
|---|---|---|
| POST | `/api/cases/{case_id}/documents` | Upload 1+ dokumen (multipart `files`) — otomatis diproses |
| GET | `/api/cases/{case_id}/documents` | Daftar dokumen milik case |
| GET | `/api/documents/{document_id}` | Detail metadata dokumen |
| GET | `/api/documents/{document_id}/preview` | Streaming file asli (PDF/JPG/PNG) untuk preview |
| GET | `/api/documents/{document_id}/text` | Hasil ekstraksi teks per halaman + extracted facts |
| POST | `/api/documents/{document_id}/process` | Proses ulang dokumen (re-run ekstraksi & klasifikasi) |
| DELETE | `/api/documents/{document_id}` | Hapus dokumen + file fisik |

### Structured Data Extraction
| Method | Endpoint | Keterangan |
|---|---|---|
| POST | `/api/cases/{case_id}/extract` | Jalankan ekstraksi LLM atas seluruh dokumen berstatus Processed pada case → simpan sebagai versi baru |
| GET | `/api/cases/{case_id}/extraction` | Ambil versi hasil ekstraksi terbaru (LLM atau hasil edit underwriter) |
| GET | `/api/cases/{case_id}/extraction/versions` | Daftar seluruh versi (LLM & edit underwriter), terbaru dulu |
| PUT | `/api/cases/{case_id}/extraction` | Simpan hasil edit underwriter sebagai versi baru (`{"data": {...}}`) |
| POST | `/api/cases/{case_id}/mock-rules` | Jalankan Mock Rule Engine terhadap versi ekstraksi terbaru |
| GET | `/api/cases/{case_id}/mock-rules` | Ambil hasil Mock Rule Engine terakhir |
| GET | `/api/llm-service/health` | Cek status LLM Extraction Service (dan provider LLM di baliknya) dari Main API |

### LLM Extraction Service (port 8001, terpisah)
| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/health` | Status service, provider aktif (`gemini`/`ollama`), ketersediaan Gemini & Ollama, model & mode |
| POST | `/extract` | Terima teks dokumen (dari Main API), kembalikan JSON terstruktur tervalidasi Pydantic |

### Lainnya
| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/api/health` | Status server & ketersediaan OCR |

### Analisis Kualitatif & Risiko Bencana Wilayah (Fitur Lanjutan)
| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/api/cases/{case_id}/regional-risk?limit=5` | Scraping berita publik (Google News RSS) terkait bencana/gangguan kondisi wilayah atas Lokasi Risiko case ini + kategorisasi & heuristik risk level (keyword matching, bukan LLM) |
| GET | `/api/cases/{case_id}/qualitative-analysis` | Merangkum seluruh hasil Disposisi Underwriting versi terbaru (Informasi Risiko, Riwayat Klaim, Subject To/Conditions, Koordinasi Cabang) digabung dengan hasil `regional-risk` di atas. Membutuhkan disposisi yang sudah di-generate terlebih dahulu (404/400 jika belum ada) |

---

## Contoh Pemakaian API (curl)

```bash
# Buat case baru
curl -X POST http://localhost:8000/api/cases \
  -H "Content-Type: application/json" \
  -d '{
        "quotation_policy_no": "QTN/2026/00999",
        "insured_name": "PT Contoh Industri",
        "risk_location": "Karawang, Jawa Barat",
        "occupation_business": "Pabrik Tekstil",
        "period_start": "2026-01-01",
        "period_end": "2027-01-01"
      }'

# Upload dokumen (bisa lebih dari satu file sekaligus)
curl -X POST http://localhost:8000/api/cases/CASE-XXXXXXXX/documents \
  -F "files=@quotation.pdf" \
  -F "files=@survey_photo.jpg"

# Lihat hasil ekstraksi teks dokumen
curl http://localhost:8000/api/documents/<document_id>/text
```

---

## Alur Pemrosesan Dokumen

1. File diunggah melalui `POST /api/cases/{case_id}/documents` (mendukung banyak file sekaligus).
2. Validasi: ekstensi harus `.pdf/.jpg/.jpeg/.png`, ukuran ≤ batas maksimum (`MAX_UPLOAD_SIZE`).
3. File disimpan secara lokal di `backend/storage/uploads/{case_id}/`.
4. Sistem otomatis memproses dokumen:
   - **PDF**: teks diekstrak per halaman menggunakan **PyMuPDF**. Jika teks pada suatu halaman kosong/di bawah ambang batas (`MIN_TEXT_LENGTH_THRESHOLD`, indikasi hasil scan), halaman tersebut dirender menjadi gambar dan diproses dengan **OCR (Tesseract)**.
   - **JPG/PNG**: langsung diproses dengan OCR.
5. Seluruh teks digabung untuk **klasifikasi jenis dokumen** berbasis kata kunci (Quotation Slip / Lembar Analisa / Survey Report / Data Aset / Dokumen Pendukung / Unknown).
6. Hasil ekstraksi disimpan per halaman (`document_pages`) beserta metode ekstraksi (`text`/`ocr`) dan jumlah karakter.
7. Dibuat **extracted facts** (`extracted_facts`) — kutipan per halaman dengan confidence score (teks langsung = 0.95, OCR = 0.75) yang selalu dapat ditelusuri ke `document_id` + `page_number` asalnya.
8. Semua histori (upload, proses, perubahan status/data case) dicatat di tabel `case_history` dengan timestamp.

---

---

## Modul Structured Data Extraction — Alur Kerja

1. Underwriter membuka **Case Detail**, lalu klik **"Extract Structured Data"** pada card yang tersedia (membutuhkan minimal satu dokumen berstatus `Processed`).
2. UI menampilkan popup progress dengan tahapan: **Preparing text → Sending to LLM → Extracting data → Validating result → Completed**.
3. Main API mengumpulkan seluruh teks hasil OCR/ekstraksi (per halaman, per dokumen) pada case tersebut, lalu mengirimkannya via HTTP ke **LLM Extraction Service** (`POST /extract`).
4. LLM Extraction Service membangun prompt terstruktur (menyertakan skema JSON & aturan "jangan mengarang, isi Not Found jika tidak ada"), lalu memutuskan provider lewat `decide_mode()`:
   - **`LLM_MODE=auto`** (default): pakai provider di `LLM_PROVIDER` (`gemini` secara default) jika siap/terkonfigurasi, else fallback mock.
   - **`LLM_MODE=gemini`**: paksa Gemini API (`google-genai` SDK, mode JSON) — fallback mock + warning jika gagal/timeout.
   - **`LLM_MODE=ollama`**: paksa Ollama lokal (`format: json`) — blueprint LLM lokal, fallback mock + warning jika tidak tersedia/gagal.
   - **`LLM_MODE=mock`**: selalu **mode mock** (heuristik keyword sederhana), untuk demo tanpa LLM/API key sama sekali.
5. Hasil (baik dari Gemini, Ollama, maupun mock) selalu melewati fungsi **`repair_result()`** yang memastikan setiap field pada skema selalu ada — field yang tidak ditemukan **selalu** diisi `"Not Found"` dengan `confidence: 0.0`, tidak pernah diisi asumsi.
6. Output divalidasi ketat menggunakan **Pydantic** (`ExtractionResult`, `FieldValue`) sebelum dikembalikan ke Main API.
7. Main API menyimpan hasil ini sebagai **versi baru** (`extraction_versions`, `source=llm`) — versi lama tidak ditimpa, sehingga histori LLM vs edit underwriter selalu terlacak.
8. Form terstruktur ditampilkan ke underwriter, dikelompokkan per kategori (Tertanggung, Lokasi Risiko, Bangunan, Aset, Proteksi Kebakaran, dst), masing-masing field menampilkan **value, evidence (kutipan), source_document, page, dan confidence**.
9. Underwriter dapat:
   - **Edit** → field menjadi dapat diedit
   - **Save Draft** → menyimpan sebagai versi baru (`source=underwriter_edit`)
   - **Cancel** → membatalkan perubahan, kembali ke versi tersimpan terakhir
   - **Re-extract** → menjalankan ulang LLM (membuat versi baru dari LLM lagi)
   - **Submit for Mock Rules** → menyimpan perubahan (jika ada) lalu menjalankan Mock Rule Engine

### Mock Rule Engine

Berbasis **konfigurasi JSON murni** (`backend/app/rules_config.json`), **bukan** LLM/RAG. Berisi:
- `critical_fields` — daftar field yang wajib terisi (untuk deteksi *missing critical information*)
- `risk_flag_rules` — kondisi sederhana (`value_in`, `not_empty_not_notfound`, `numeric_gte`, `numeric_lte`) yang memicu risk flag & menaikkan risk level
- `consistency_checks` — pengecekan konsistensi sederhana antar field (mis. `assets.sum_insured_total` vs `coverage.sum_insured`)
- `recommended_actions` — pemetaan risk level → rekomendasi tindakan

Hasil evaluasi (`risk_level`, `risk_flags`, `missing_critical_info`, `data_inconsistencies`, `recommended_action`) disimpan di tabel `mock_rules_results`, tertaut ke versi ekstraksi yang dievaluasi.

Anda bisa menyesuaikan aturan risiko cukup dengan mengedit `backend/app/rules_config.json` — tidak perlu mengubah kode.

---

## Analisis Kualitatif & Risiko Bencana Wilayah

Dua kemampuan tambahan yang tersedia pada Case Detail, setelah Disposisi Underwriting di-generate:

1. **Analisis Risiko Bencana Wilayah** (`backend/app/services/regional_risk_service.py`) — mengambil berita publik terkini terkait **Lokasi Risiko** case (banjir, gempa, kebakaran hutan, longsor, kerusuhan/demo, konflik lahan, pemadaman listrik, dst) dari **Google News RSS** murni via **web scraping** (`httpx` + `xml.etree.ElementTree` + `BeautifulSoup`), lalu setiap berita dikategorikan dengan **keyword matching sederhana** (bukan NLP/LLM) dan dihitung `risk_level` heuristik (`Low`/`Medium`/`High`) berdasarkan jumlah & jenis berita yang terdeteksi. Setiap berita menyertakan judul, cuplikan, tanggal, dan **URL sumber asli** agar dapat ditelusuri/diverifikasi oleh underwriter.
2. **Analisis Kualitatif** (`disposition_service.build_qualitative_analysis_data`) — merangkum **seluruh** komponen Disposisi Underwriting versi terbaru (Informasi Risiko, Riwayat Klaim, Subject To/Conditions per kategori, Rekomendasi, Koordinasi Cabang) dan menggabungkannya dengan hasil Analisis Risiko Bencana Wilayah di atas menjadi satu rangkuman, lengkap dengan kesimpulan kualitatif singkat. Sama seperti Mock Rule Engine & Subject To Rule Engine, proses ini murni **agregasi/template dari data yang sudah ada** — **tidak menggunakan LLM**.

> **Catatan:** hasil Analisis Risiko Bencana Wilayah bersifat **indikatif** (berdasarkan pemberitaan publik, bukan data resmi BMKG/BNPB atau hasil survey lapangan) dan membutuhkan **koneksi internet** dari server Main API ke `news.google.com` — bila server tidak memiliki akses internet atau tidak ada berita relevan yang ditemukan, `risk_level` akan tetap ditampilkan sebagai `Low` disertai `warning` yang menjelaskan bahwa ini bukan kepastian tidak ada risiko, bukan gagal secara diam-diam.

---

## Skema Database (ringkas)

```
Case (1) ──< Document (N)
Document (1) ──< DocumentPage (N)
Document (1) ──< ExtractedFact (N)
Case (1) ──< CaseHistory (N)
Case (1) ──< ExtractionVersion (N)         [baru]
ExtractionVersion (1) ──< MockRulesResult (N) [baru]
```

- **cases**: id, quotation_policy_no, insured_name, risk_location, occupation_business, period_start, period_end, status, created_at, updated_at
- **documents**: id, case_id, original_filename, doc_type, file_format, file_size, page_count, processing_status, storage_path, uploaded_at, processed_at
- **document_pages**: id, document_id, page_number, extracted_text, extraction_method, char_count
- **extracted_facts**: id, document_id, document_type, page_number, extracted_text, confidence_score, created_at
- **case_history**: id, case_id, action, description, old_value, new_value, created_at
- **extraction_versions** *(baru)*: id, case_id, version_number, source (`llm`/`underwriter_edit`), method, model_name, data_json (JSON `ExtractionResult` lengkap), warnings_json, created_at
- **mock_rules_results** *(baru)*: id, case_id, extraction_version_id, risk_level, risk_flags_json, missing_critical_json, inconsistencies_json, recommended_action, created_at

Setiap kali LLM dijalankan (extract/re-extract) atau underwriter menyimpan perubahan (Save Draft), baris baru ditambahkan ke `extraction_versions` (append-only, tidak pernah menimpa) — sehingga versi hasil LLM murni dan versi hasil edit underwriter selalu bisa dibandingkan/ditelusuri.

---

## Konfigurasi `.env` — LLM Extraction Service (`llm-service/.env`)

| Variabel | Default | Keterangan |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Provider yang dipakai saat `LLM_MODE=auto`: `gemini` (default, cloud) atau `ollama` (blueprint LLM lokal) |
| `GEMINI_API_KEY` | *(kosong)* | API key Gemini — buat di https://aistudio.google.com/apikey. Jika kosong, SDK juga otomatis membaca env `GOOGLE_API_KEY` |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Model Gemini yang dipakai — cek model/alias terbaru di https://ai.google.dev/gemini-api/docs/models |
| `GEMINI_TIMEOUT` | `120` | Timeout request ke Gemini API (detik) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Alamat server Ollama (blueprint LLM lokal) |
| `OLLAMA_MODEL` | `llama3.1` | Model Ollama yang digunakan (harus sudah `ollama pull`) |
| `OLLAMA_TIMEOUT` | `180` | Timeout request ke Ollama (detik) |
| `LLM_MODE` | `auto` | `auto` (pakai provider di `LLM_PROVIDER`, else mock) / `gemini` atau `ollama` (paksa provider tsb., fallback mock+warning jika gagal) / `mock` (selalu mock) |
| `PORT` | `8001` | Port service ini |
| `CORS_ORIGINS` | `*` | Origin yang diizinkan CORS |

## Konfigurasi `.env` tambahan — Main API (`backend/.env`)

| Variabel | Default | Keterangan |
|---|---|---|
| `LLM_SERVICE_URL` | `http://localhost:8001` | Alamat LLM Extraction Service |
| `LLM_SERVICE_TIMEOUT` | `200` | Timeout request Main API → LLM Extraction Service (detik) |

---

## Konfigurasi (.env)

Salin `backend/.env.example` menjadi `backend/.env` untuk menyesuaikan:

| Variabel | Default | Keterangan |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./storage/underwriting.db` | Lokasi database |
| `STORAGE_DIR` | `./storage/uploads` | Direktori penyimpanan file |
| `MAX_UPLOAD_SIZE` | `26214400` (25MB) | Batas ukuran file upload |
| `TESSERACT_CMD` | (kosong) | Path binary tesseract jika tidak ada di PATH |
| `MIN_TEXT_LENGTH_THRESHOLD` | `20` | Ambang batas karakter untuk memicu fallback OCR |
| `FRONTEND_DIR` | `../frontend` | Direktori frontend statis |
| `CORS_ORIGINS` | `*` | Origin yang diizinkan CORS |

---

## Catatan Implementasi & Batasan

- Klasifikasi jenis dokumen (Modul 2) menggunakan **pencocokan kata kunci sederhana**, bukan model AI/LLM.
- Modul Structured Data Extraction menggunakan LLM (**Gemini API** secara default; **Ollama lokal dipertahankan sebagai blueprint**, aktifkan via `LLM_PROVIDER=ollama`) **hanya** untuk mengisi form data dari teks yang sudah diekstrak — **tidak** ada RAG, dan Mock Rule Engine **bukan** analisa underwriting LLM sesungguhnya, hanya evaluasi kondisi sederhana berbasis `rules_config.json`.
- Karena Gemini adalah API cloud pihak ketiga (bukan model lokal seperti Ollama), teks dokumen yang dikirim untuk ekstraksi akan keluar dari infrastruktur lokal ke server Google. Pertimbangkan implikasi ini untuk dokumen yang bersifat rahasia/sensitif, dan tinjau kebijakan data Gemini API (https://ai.google.dev/gemini-api/docs/logs-policy) sebelum dipakai dengan data produksi sungguhan.
- Field yang tidak ditemukan LLM/mock **selalu** diisi `"Not Found"` dengan confidence `0.0` — sistem tidak pernah mengarang nilai.
- LLM Extraction Service **tidak memiliki akses ke database utama** — komunikasi murni via HTTP API (`/extract`), sesuai prinsip pemisahan service.
- Setiap perubahan pada hasil ekstraksi (baik dari LLM maupun edit underwriter) disimpan sebagai **versi baru** (append-only) di `extraction_versions`, sehingga histori selalu utuh dan dapat dibandingkan.
- Upload mendukung banyak file sekaligus dan setiap file diproses secara independen (bila satu file gagal, file lain tetap diproses; hasil dilaporkan dalam response `uploaded` & `failed`).
- File fisik disimpan secara lokal di `backend/storage/uploads/{case_id}/`, dikelompokkan per case.
- Semua perubahan (create/update case, ubah status, upload/proses/hapus dokumen, ekstraksi, edit, mock rules) dicatat otomatis ke `case_history` dengan timestamp.
- Data dummy (4 case contoh) otomatis diisi saat pertama kali database dibuat, khusus untuk kebutuhan pengujian.
