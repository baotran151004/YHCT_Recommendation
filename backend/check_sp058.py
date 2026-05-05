import os
import sys
os.environ['DATABASE_URL'] = 'postgresql://postgres:riZTueCAvXKxSOVJDfewTUGDdDaosgeZ@interchange.proxy.rlwy.net:49607/railway'
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'd:\\LATN\\yhct_recommentder\\backend')
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("--- 7. PRINCIPLES FOR SP058 (Tỳ vị hư hàn) ---")
    res = conn.execute(text("SELECT pp.principle_id, tp.principle_name_vi FROM patternprinciple pp JOIN therapeuticprinciple tp ON tp.principle_id = pp.principle_id WHERE pp.pattern_id = 'SP058'"))
    for r in res.fetchall():
        print(f"{r[0]}: {r[1]}")
    
    print("\n--- 8. FORMULAS FOR THOSE PRINCIPLES ---")
    res = conn.execute(text("SELECT fp.formula_id, f.formula_name_vi FROM formulaprinciple fp JOIN formula f ON f.formula_id = fp.formula_id WHERE fp.principle_id IN (SELECT principle_id FROM patternprinciple WHERE pattern_id = 'SP058')"))
    for r in res.fetchall():
        print(f"{r[0]}: {r[1]}")
