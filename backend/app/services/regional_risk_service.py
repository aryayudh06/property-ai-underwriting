"""
Analisis Risiko Bencana Wilayah (Lokasi Risiko).

Mengambil sinyal risiko bencana/gangguan kondisi wilayah (banjir, gempa,
kebakaran hutan, longsor, kerusuhan, konflik lahan, pemadaman listrik, dst)
dari BERITA PUBLIK (Google News RSS) via web scraping sederhana, lalu
mengkategorikan tiap berita dengan keyword matching sederhana - BUKAN LLM,
BUKAN model AI/NLP apa pun. Prinsipnya sama dengan claim_search_service.py
(query sumber data nyata) & subject_to_engine.py (rule/keyword berbasis
konfigurasi) - hasil selalu dapat ditelusuri ke URL berita aslinya.

PENTING - keterbatasan:
- Hasil bersifat INDIKATIF berdasarkan judul & cuplikan berita yang mengandung
  kata kunci terkait wilayah + bencana/gangguan - BUKAN analisa risiko bencana
  resmi (mis. dari BMKG/BNPB) dan BUKAN pengganti survey/asesmen lapangan.
- Bergantung pada ketersediaan & pemberitaan Google News - wilayah kecil/tidak
  banyak diberitakan bisa saja tidak menghasilkan berita meski risikonya nyata,
  begitu pula sebaliknya berita lama/tidak relevan bisa saja ikut terambil.
- Wajib diverifikasi lebih lanjut oleh underwriter/surveyor sebelum dipakai
  sebagai dasar keputusan akseptasi.
"""
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Hasil pemantauan berita publik (Google News RSS), bersifat INDIKATIF - "
    "bukan analisa risiko bencana resmi (mis. BMKG/BNPB) atau hasil survey "
    "lapangan. Wajib diverifikasi lebih lanjut oleh underwriter/surveyor "
    "sebelum dipakai sebagai dasar keputusan akseptasi."
)

# Kategori risiko wilayah & kata kunci pemicunya - keyword matching sederhana
# atas judul+cuplikan berita, selaras dengan gaya klasifikasi dokumen
# (document_processor.py) & Mock Rule Engine (mock_rules_engine.py) di app
# ini: berbasis konfigurasi/kata kunci, bukan NLP/LLM.
RISK_KEYWORDS = {
    "Kebakaran Hutan/Lahan": ["kebakaran hutan", "karhutla", "kebakaran lahan"],
    "Banjir": ["banjir"],
    "Tanah Longsor": ["longsor"],
    "Gempa Bumi": ["gempa", "tsunami"],
    "Bencana Umum": ["bencana", "darurat bencana", "siaga bencana"],
    "Kerusuhan/Demo": ["kerusuhan", "demo", "unjuk rasa", "bentrok"],
    "Konflik Lahan": ["konflik lahan", "sengketa lahan", "sengketa tanah"],
    "Pemadaman Listrik": ["pemadaman listrik", "padam listrik", "byar pet"],
}

# Kategori yang dianggap "berdampak tinggi" bila terdeteksi - heuristik
# ilustratif sederhana (bukan perhitungan probabilistik), selaras dengan
# risk_level pada rules_config.json/mock_rules_engine.py.
HIGH_SEVERITY_CATEGORIES = {
    "Gempa Bumi", "Bencana Umum", "Kebakaran Hutan/Lahan", "Tanah Longsor", "Banjir",
}


async def _scrape_regional_news(wilayah: str, limit: int = 5) -> list[dict]:
    """Ambil berita terbaru terkait gangguan/risiko kondisi wilayah dari Google News RSS."""
    query = (
        f'"{wilayah}" (kebakaran hutan OR banjir OR longsor OR gempa OR bencana '
        f'OR kerusuhan OR demo OR konflik lahan OR pemadaman listrik)'
    )
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=id&gl=ID&ceid=ID:id"

    results = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.text)

            for item in root.findall(".//item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                description_html = item.findtext("description") or ""
                snippet = BeautifulSoup(description_html, "html.parser").get_text(strip=True)
                results.append({
                    "title": title,
                    "snippet": snippet or pub_date,
                    "url": link,
                    "pub_date": pub_date,
                })
    except Exception as e:
        logger.warning(f"[Warning] Google News RSS (regional) error: {e}")

    return results


def _detect_categories(text: str) -> list[str]:
    """Cocokkan teks (judul + cuplikan) terhadap RISK_KEYWORDS - keyword
    matching sederhana, tidak pernah menyimpulkan kategori di luar daftar."""
    text_lower = (text or "").lower()
    return [
        category for category, keywords in RISK_KEYWORDS.items()
        if any(kw in text_lower for kw in keywords)
    ]


def _determine_risk_level(categorized_news: list[dict]) -> str:
    """
    Heuristik SEDERHANA berbasis jumlah berita terdeteksi & ada/tidaknya
    kategori berdampak tinggi - ilustratif, sama seperti risk_level pada
    mock_rules_engine.py. BUKAN model prediktif/AI.
    """
    if not categorized_news:
        return "Low"

    has_high_severity = any(
        cat in HIGH_SEVERITY_CATEGORIES
        for item in categorized_news
        for cat in item["categories"]
    )
    if has_high_severity and len(categorized_news) >= 2:
        return "High"
    if has_high_severity or len(categorized_news) >= 2:
        return "Medium"
    return "Low"


async def analyze_regional_disaster_risk(wilayah: str, limit: int = 5) -> dict:
    """
    Orkestrasi penuh: web scraping berita publik (Google News RSS) atas nama
    wilayah -> deteksi kategori risiko bencana/gangguan per berita (keyword
    matching) -> heuristik risk_level. Murni scraping + rule sederhana,
    TIDAK memanggil LLM/model AI sama sekali.
    """
    wilayah = (wilayah or "").strip()
    checked_at = datetime.now(timezone.utc).isoformat()
    base = {
        "wilayah": wilayah,
        "checked_at": checked_at,
        "source": "Google News RSS (news.google.com)",
        "method": "web_scraping_keyword_heuristic",
        "disclaimer": DISCLAIMER,
    }

    if not wilayah:
        return {
            **base,
            "risk_level": "Unknown",
            "risk_categories_detected": [],
            "news_items": [],
            "warning": "Lokasi risiko (wilayah) kosong pada data case - tidak dapat melakukan pencarian berita.",
        }

    raw_news = await _scrape_regional_news(wilayah, limit=limit)

    news_items = []
    for n in raw_news:
        categories = _detect_categories(f"{n['title']} {n['snippet']}")
        news_items.append({**n, "categories": categories})

    all_categories = sorted({cat for n in news_items for cat in n["categories"]})
    risk_level = _determine_risk_level(news_items)

    warning = None
    if not raw_news:
        warning = (
            "Tidak ditemukan berita terkait wilayah ini, atau gagal mengambil data dari "
            "Google News RSS (periksa koneksi internet server). risk_level ditampilkan "
            "sebagai indikasi minimal (Low) - BUKAN kepastian tidak ada risiko bencana."
        )

    return {
        **base,
        "risk_level": risk_level,
        "risk_categories_detected": all_categories,
        "news_items": news_items,
        "warning": warning,
    }
