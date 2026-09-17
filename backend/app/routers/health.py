from datetime import datetime

from fastapi import APIRouter

from app.services import ocr_service

router = APIRouter(tags=["Health"])


@router.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "ocr_available": ocr_service.is_ocr_available(),
    }
