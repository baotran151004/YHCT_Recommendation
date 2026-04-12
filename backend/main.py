from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
import logging
import sys
import traceback

# Force UTF-8 encoding for Windows console compatibility
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Project internal imports
import models, schemas, crud, auth
from database import engine, SessionLocal, Base
from dependency import get_db, get_current_user, require_role
from security import sanitize_and_check_input
from semantic_expert_system import SemanticExpertSystemEngine
from seed import seed_data

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
def startup_event() -> None:
    print("\n" + "="*50)
    print("[startup] Connecting to PostgreSQL (Railway)...")
    
    # 1. Create Tables (Base.metadata.create_all)
    try:
        Base.metadata.create_all(bind=engine)
        print("[startup] Tables created / verified in PostgreSQL.")
    except Exception as exc:
        print("[startup] CRITICAL: Error creating tables:")
        traceback.print_exc()
        raise

    # 2. Seed data if tables are empty
    try:
        with SessionLocal() as db:
            seed_data(db)
    except Exception as exc:
        print(f"[startup] WARNING: Error during seeding: {exc}")

    # 3. Load expert system after data is ready
    print("[startup] Loading expert system data...")
    try:
        expert_engine.load(SessionLocal)
        if expert_engine.ready:
            print("[startup] Expert system loaded successfully.")
        else:
            print("[startup] WARNING: Expert system loaded but reported AS NOT READY.")
    except Exception as exc:
        print("[startup] ERROR: Expert system failed to load:")
        traceback.print_exc()
        expert_engine.ready = False

    print("="*50 + "\n")

@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "expert_system": {
            "ready": expert_engine.ready,
            "symptoms_count": len(expert_engine.symptoms),
            "patterns_count": len(expert_engine.patterns),
            "formulas_count": len(expert_engine.formulas),
            "aliases_count": len(expert_engine.alias_entries),
            "pattern_symptom_source": getattr(expert_engine, "pattern_symptom_source", "none"),
            "encoder_backend": getattr(expert_engine, "encoder_backend", "none"),
        }
    }

# --- AUTH ENPOINTS ---

@app.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Public registration for new users."""
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = crud.create_user(db=db, user=user)
    access_token = auth.create_access_token(data={"sub": new_user.username, "role": new_user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Standard OAuth2 compatible login."""
    user = crud.authenticate_user(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# --- SEARCH & HISTORY ENDPOINTS ---

@app.get("/history", response_model=List[schemas.SearchHistoryOut])
def get_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Retrieve search history for the logged-in user."""
    return crud.get_user_history(db, user_id=current_user.user_id)

@app.get("/suggest-symptoms", response_model=List[schemas.SymptomSuggest])
def suggest_symptoms(q: str = "", current_user: models.User = Depends(get_current_user)):
    """Suggest symptoms based on query string."""
    return expert_engine.suggest_symptoms(q, limit=10)

@app.get("/expert-system/recommend")
@limiter.limit("20/minute")
def expert_system_inference(
    request: Request,
    symptom: str = Depends(sanitize_and_check_input),
    top_k: int = 1,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Core AI recommendation endpoint. 
    Requires authentication and automatically saves search history.
    """
    if not symptom or not symptom.strip():
        return []

    if not expert_engine.ready:
        raise HTTPException(
            status_code=503, 
            detail="Expert system is not ready. Check /health for details."
        )

    # 1. Log search to console
    logger.info(f"User {current_user.username} searched: {symptom}")

    # 2. Auto-save search to database
    crud.save_search(db, user_id=current_user.user_id, query=symptom)

    requested_top_k = max(1, min(top_k, 3))

    try:
        return expert_engine.recommend(symptom, top_k=requested_top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Log the full error to the console for the administrator
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Expert System error.") from exc

# --- ADMIN ENDPOINTS ---

@app.get("/admin/users", response_model=List[schemas.UserOut])
def get_users(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_role(["admin"]))
):
    return db.query(models.User).all()

@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
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
