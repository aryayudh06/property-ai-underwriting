from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, FRONTEND_DIR
from app.database import Base, engine, SessionLocal
from app.routers import cases, documents, health, extraction, claims, knowledge, disposition, regional_risk
from app import seed

app = FastAPI(
    title="Property AI Underwriting Assistant - Prototype API",
    description="Case Management & Document Processing (tanpa LLM/RAG/rules engine)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed.seed_dummy_data(db)
    finally:
        db.close()


# ---- API routers ----
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(claims.router)
app.include_router(knowledge.router)
app.include_router(disposition.router)
app.include_router(regional_risk.router)

# ---- Static frontend (vanilla HTML/CSS/JS) ----
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
