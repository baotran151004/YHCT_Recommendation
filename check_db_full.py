from database import SessionLocal
from sqlalchemy import text
import sys

try:
    print("Trying to connect to DB...")
    db = SessionLocal()
    
    # 1. Check SymptomAlias & Symptom
    res = db.execute(text("SELECT TOP 1 * FROM SymptomAlias"))
    print("SUCCESS: Queried SymptomAlias")
    
    res2 = db.execute(text("SELECT TOP 1 * FROM Symptom"))
    print("SUCCESS: Queried Symptom")
    
    # 2. Check Formula
    res3 = db.execute(text("SELECT TOP 1 formula_id, formula_name_vi, formula_category, indications FROM Formula"))
    print("SUCCESS: Queried Formula")
    
    # 3. Check Join Query (Multiple tables)
    res4 = db.execute(text("""
        SELECT TOP 1 f.formula_id, sp.clinical_manifestations
        FROM Formula f
        JOIN FormulaPrinciple fp ON f.formula_id = fp.formula_id
        JOIN PatternPrinciple pp ON pp.principle_id = fp.principle_id
        JOIN SyndromePattern sp ON sp.pattern_id = pp.pattern_id
    """))
    print("SUCCESS: Queried Join (Formula, FormulaPrinciple, PatternPrinciple, SyndromePattern)")
    
    db.close()
    print("✅ DATABASE CONNECTION AND TABLES ARE OK")
except Exception as e:
    print("ERROR detail:")
    print(e)
    sys.exit(1)
