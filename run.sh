#!/usr/bin/env bash
# Menjalankan Property AI Underwriting Assistant (Main API + Frontend) secara lokal.
#
# CATATAN: Modul "Structured Data Extraction" membutuhkan LLM Extraction Service
# (port 8001) berjalan terpisah. Jalankan di terminal lain:
#     ./run_llm_service.sh
# Tanpa service tersebut, tombol "Extract Structured Data" akan menampilkan error
# (fitur upload/OCR/case management tetap berjalan normal seperti biasa).
set -e

cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo ">> Membuat virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo ">> Menginstall dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
fi

echo ">> Menjalankan server di http://localhost:8000 ..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
