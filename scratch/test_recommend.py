
import sys
import os
import json
from sqlalchemy.orm import Session
from database import SessionLocal
from semantic_expert_system import SemanticExpertSystemEngine

def test_recommend():
    engine = SemanticExpertSystemEngine()
    engine.load(SessionLocal)
    
    # Test with a known symptom
    results = engine.recommend("ho")
    print(f"Recommend results for 'ho':")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    if results:
        res = results[0]
        # Check for expected keys
        expected_keys = [
            "name", "confidence", "score", "pattern", "principle", 
            "explain", "normalized_symptoms", "composition"
        ]
        for key in expected_keys:
            if key not in res:
                print(f"MISSING KEY: {key}")
            else:
                print(f"Found key: {key}")
    else:
        print("No results returned for 'ho'. Check if data is seeded.")

if __name__ == "__main__":
    test_recommend()
