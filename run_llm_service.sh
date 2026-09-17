#!/usr/bin/env bash
# Menjalankan LLM Extraction Service (port 8001) secara lokal.
# Service ini terpisah dari Main API dan berkomunikasi dengan Ollama.
set -e

cd "$(dirname "$0")/llm-service"

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

echo ">> Menjalankan LLM Extraction Service di http://localhost:8001 ..."
echo ">> (Mode mengikuti LLM_MODE di .env: auto/ollama/mock)"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
