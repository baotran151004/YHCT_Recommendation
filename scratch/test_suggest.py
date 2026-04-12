
import sys
import os
from sqlalchemy.orm import Session
from database import SessionLocal
from semantic_expert_system import SemanticExpertSystemEngine

def test_suggest():
    engine = SemanticExpertSystemEngine()
    engine.load(SessionLocal)
    
    results = engine.suggest_symptoms("đau")
    print(f"Results for 'đau': {results}")
    
    for r in results:
        if not isinstance(r.get('symptom_name'), str):
            print(f"CRITICAL: symptom_name is NOT a string! Type: {type(r.get('symptom_name'))}")
        else:
            print(f"OK: {r.get('symptom_name')}")

if __name__ == "__main__":
    test_suggest()
