from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Refactored imports
import models, schemas, crud, auth
from database import engine, SessionLocal
from dependency import get_db, get_current_user, require_role
from security import sanitize_and_check_input
from semantic_expert_system import SemanticExpertSystemEngine

# Initialize database
models.Base.metadata.create_all(bind=engine)

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
        "diagnostic_mode": "semantic",
        "encoder_backend": getattr(expert_engine, "encoder_backend", "none"),
    }

@app.post("/register", response_model=schemas.Token)
def register(
    user: schemas.UserCreate, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_role(["admin"]))
):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = crud.create_user(db=db, user=user)
    
    access_token = auth.create_access_token(data={"sub": new_user.user_id, "role": new_user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    access_token = auth.create_access_token(data={"sub": user.user_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/admin/users", response_model=List[schemas.UserOut])
def get_users(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_role(["admin"]))
):
    return db.query(models.User).all()

@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_role(["admin"]))
):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.user_id == current_admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}

@app.get("/suggest-symptoms")
def suggest_symptoms(q: str = "", current_user: models.User = Depends(require_role(["doctor", "admin"]))):
    return expert_engine.suggest_symptoms(q, limit=10)

@app.get("/expert-system/recommend")
@limiter.limit("20/minute")
def expert_system_inference(
    request: Request,
    symptom: str = Depends(sanitize_and_check_input),
    top_k: int = 1,
    current_user: models.User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    if not symptom or not symptom.strip():
        return []

    # Audit log using crud function
    crud.create_search_history(db, user_id=current_user.user_id, query=symptom)

    requested_top_k = max(1, min(top_k, 3))

    try:
        return expert_engine.recommend(symptom, top_k=requested_top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Expert system error: {exc}") from exc
