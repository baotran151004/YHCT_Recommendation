from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import uuid
from typing import Optional, List
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from schemas import UserRegister, Token, UserOut
from auth import get_password_hash, verify_password, create_access_token, get_db, get_current_user, require_role
from security import sanitize_and_check_input
from models import User, SearchHistory, Base
from database import engine

from database import SessionLocal
from semantic_expert_system import SemanticExpertSystemEngine

Base.metadata.create_all(bind=engine)
limiter = Limiter(key_func=get_remote_address)


app = FastAPI(title="YHCT Semantic Expert System")
expert_engine = SemanticExpertSystemEngine()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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


@app.post("/register", response_model=Token)
def register(
    user: UserRegister, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    db_user = User(
        user_id=user_id,
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token = create_access_token(data={"sub": user_id, "role": db_user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/admin/users", response_model=List[UserOut])
def get_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
):
    return db.query(User).all()


@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.user_id == current_admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    access_token = create_access_token(data={"sub": user.user_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/suggest-symptoms")
def suggest_symptoms(q: str = ""):
    return expert_engine.suggest_symptoms(q, limit=10)


@app.get("/expert-system/recommend")
@limiter.limit("20/minute")
def expert_system_inference(
    request: Request,
    symptom: str = Depends(sanitize_and_check_input),
    top_k: int = 1,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    if not symptom or not symptom.strip():
        return []

    # Audit log
    search_log = SearchHistory(user_id=current_user.user_id, query_text=symptom)
    db.add(search_log)
    db.commit()

    requested_top_k = max(1, min(top_k, 3))

    try:
        return expert_engine.recommend(symptom, top_k=requested_top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert system error: {exc}") from exc
