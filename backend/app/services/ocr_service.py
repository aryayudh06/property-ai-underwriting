"""
Layanan OCR. Menggunakan Tesseract (via pytesseract) untuk gambar,
dan PyMuPDF untuk merender halaman PDF hasil scan menjadi gambar sebelum di-OCR.

OCR hanya dipanggil jika ekstraksi teks langsung dari PDF tidak tersedia
atau tidak memadai (lihat document_processor.py).
"""
from io import BytesIO
from pathlib import Path

from app.config import TESSERACT_CMD

_OCR_AVAILABLE = True
_OCR_IMPORT_ERROR = None

try:
    import pytesseract
    from PIL import Image

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
except Exception as e:  # pragma: no cover
    _OCR_AVAILABLE = False
    _OCR_IMPORT_ERROR = str(e)


def _diagnose_unavailable() -> str:
    """Bangun pesan error yang lebih spesifik agar mudah di-debug."""
    if not _OCR_AVAILABLE:
        return f"Modul OCR gagal di-import: {_OCR_IMPORT_ERROR}"

    if TESSERACT_CMD:
        if not Path(TESSERACT_CMD).exists():
            return (
                f"TESSERACT_CMD di .env menunjuk ke path yang tidak ditemukan: "
                f"'{TESSERACT_CMD}'. Periksa kembali lokasi file tesseract.exe."
            )
        return (
            f"TESSERACT_CMD sudah diset ke '{TESSERACT_CMD}' dan file ditemukan, "
            f"tetapi tesseract gagal dijalankan (cek permission atau instalasi rusak)."
        )

    return (
        "Tesseract tidak ditemukan di PATH sistem, dan TESSERACT_CMD belum diset. "
        "Set TESSERACT_CMD di file backend/.env menuju lokasi tesseract.exe, "
        "lalu restart server."
    )


def is_ocr_available() -> bool:
    if not _OCR_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_image_bytes(image_bytes: bytes, lang: str = "eng+ind") -> str:
    """Jalankan OCR pada bytes gambar (jpg/png) dan kembalikan teks."""
    if not is_ocr_available():
        raise RuntimeError(_diagnose_unavailable())
    image = Image.open(BytesIO(image_bytes))
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except Exception:
        # fallback jika bahasa 'ind' belum terpasang
        return pytesseract.image_to_string(image, lang="eng")


def ocr_pdf_page(fitz_page, dpi: int = 200) -> str:
    """Render satu halaman PDF (objek fitz.Page) menjadi gambar, lalu OCR."""
    zoom = dpi / 72
    matrix = _fitz_matrix(zoom)
    pix = fitz_page.get_pixmap(matrix=matrix)
    img_bytes = pix.tobytes("png")
    return ocr_image_bytes(img_bytes)


def _fitz_matrix(zoom):
    import fitz  # PyMuPDF
    return fitz.Matrix(zoom, zoom)
