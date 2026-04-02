from database import SessionLocal
from models import *
from sqlalchemy import or_

def recommend_by_symptom(symptom):
    db = SessionLocal()

    results = db.query(Formula)\
    .join(FormulaPrinciple)\
    .join(TherapeuticPrinciple)\
    .join(PatternPrinciple)\
    .join(SyndromePattern)\
    .filter(
        SyndromePattern.pattern_name_vi.ilike(f"%{symptom}%")
    )\
    .order_by(PatternPrinciple.priority_level.desc())\
    .limit(10)\
    .all()

    # remove duplicate
    unique = {f.formula_id: f for f in results}.values()

    return list(unique)