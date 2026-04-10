from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal
from semantic_expert_system import SemanticExpertSystemEngine


app = FastAPI(title="YHCT Semantic Expert System")
expert_engine = SemanticExpertSystemEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_expert_system() -> None:
    try:
        expert_engine.load(SessionLocal)
    except Exception as exc:
        print(f"[expert-system] startup failed: {exc}")
        raise


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "expert_system_ready": expert_engine.ready,
        "patterns": len(expert_engine.patterns),
        "formulas": len(expert_engine.formulas),
        "pattern_symptom_source": getattr(expert_engine, "pattern_symptom_source", "unknown"),
        "diagnostic_mode": "semantic",
        "semantic_enabled": expert_engine.encoder_backend is not None,
        "encoder_backend": getattr(expert_engine, "encoder_backend", "none"),
    }


@app.get("/suggest-symptoms")
def suggest_symptoms(q: str = ""):
    return expert_engine.suggest_symptoms(q, limit=10)


@app.get("/expert-system/recommend")
def expert_system_inference(symptom: str, top_k: int = 1):
    if not symptom or not symptom.strip():
        return []

    requested_top_k = max(1, min(top_k, 3))

    try:
        return expert_engine.recommend(symptom, top_k=requested_top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert system error: {exc}") from exc
