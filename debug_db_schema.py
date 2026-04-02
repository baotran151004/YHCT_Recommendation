from database import SessionLocal
from sqlalchemy import text
import sys

def check_table(db, table_name):
    print(f"\nChecking table: {table_name}")
    try:
        res = db.execute(text(f"SELECT TOP 1 * FROM {table_name}"))
        print(f"✅ Table {table_name} exists. Keys: {res.keys()}")
    except Exception as e:
        print(f"❌ Table {table_name} ERROR: {e}")

try:
    db = SessionLocal()
    check_table(db, "Formula")
    check_table(db, "FormulaPrinciple")
    check_table(db, "PatternPrinciple")
    check_table(db, "SyndromePattern")
    
    # Check the specific problematic join
    print("\nChecking Join query...")
    try:
        db.execute(text("""
            SELECT TOP 1 f.formula_id, sp.clinical_manifestations
            FROM Formula f
            JOIN FormulaPrinciple fp ON f.formula_id = fp.formula_id
            JOIN PatternPrinciple pp ON pp.principle_id = fp.principle_id
            JOIN SyndromePattern sp ON sp.pattern_id = pp.pattern_id
        """))
        print("✅ Join query SUCCESS")
    except Exception as e:
        print(f"❌ Join query ERROR: {e}")
        
    db.close()
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
