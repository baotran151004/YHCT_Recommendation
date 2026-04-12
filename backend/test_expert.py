import os
import sys
from dotenv import load_dotenv

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

from database import SessionLocal
from semantic_expert_system import SemanticExpertSystemEngine

def test_recommender():
    engine = SemanticExpertSystemEngine()
    print("Loading data...")
    engine.load(SessionLocal)
    
    if not engine.ready:
        print("Engine NOT READY")
        return

    test_cases = [
        "đau đầu",
        "phát sốt, đau đầu, sợ gió",
        "đau đầu, tay chân lạnh, thích ấm",  # Conflict logic check
        "đau bụng, đi ngoài, chân tay lạnh",
        "xyz non-existent symptom"
    ]

    for query in test_cases:
        print(f"\nQUERY: {query}")
        result = engine.recommend(query)
        if "error" in result:
            print(f"RESULT: Error - {result['error']}")
        else:
            print(f"FORMULA: {result['formula']}")
            print(f"SCORE: {result['score']}")
            print(f"EXPLANATION:\n{result['explanation']}")

if __name__ == "__main__":
    test_recommender()
