import os
import sys
os.environ['DATABASE_URL'] = 'postgresql://postgres:riZTueCAvXKxSOVJDfewTUGDdDaosgeZ@interchange.proxy.rlwy.net:49607/railway'
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'd:\\LATN\\yhct_recommentder\\backend')

from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("--- 1. SYMPTOMS ---")
    symptoms_to_check = ["đau bụng", "tiêu chảy", "đi ngoài", "đau dạ dày", "xuất huyết", "chảy máu"]
    for sym in symptoms_to_check:
        res = conn.execute(text("SELECT symptom_id, symptom_name FROM symptom WHERE symptom_name ILIKE :sym"), {"sym": f"%{sym}%"})
        rows = res.fetchall()
        print(f"'{sym}':", rows)

    print("\n--- 2. HOÀNG THỔ THANG MAPPING ---")
    res = conn.execute(text("SELECT formula_id, formula_name_vi, formula_category, function_tcm FROM formula WHERE formula_name_vi ILIKE '%Hoàng thổ thang%'"))
    ht_formulas = res.fetchall()
    print("Formulas:", ht_formulas)
    
    if ht_formulas:
        f_id = ht_formulas[0][0]
        # Check principles linked to Hoàng thổ thang
        res = conn.execute(text("""
            SELECT fp.principle_id, tp.principle_name_vi 
            FROM formulaprinciple fp 
            JOIN therapeuticprinciple tp ON tp.principle_id = fp.principle_id 
            WHERE fp.formula_id = :fid
        """), {"fid": f_id})
        tp_rows = res.fetchall()
        print("Principles mapped to Hoàng thổ thang:", tp_rows)
        
        # Check patterns linked to those principles
        for tp in tp_rows:
            tp_id = tp[0]
            res = conn.execute(text("""
                SELECT pp.pattern_id, sp.pattern_name_vi 
                FROM patternprinciple pp 
                JOIN syndromepattern sp ON sp.pattern_id = pp.pattern_id 
                WHERE pp.principle_id = :tpid
            """), {"tpid": tp_id})
            pat_rows = res.fetchall()
            print(f"Patterns mapped to principle {tp[1]} ({tp_id}):", pat_rows)

    print("\n--- 3. NHỊ TRẦN THANG / BÁN HẠ MAPPING ---")
    for f_name in ["Nhị trần thang", "Bán hạ bạch truật thiên ma thang"]:
        res = conn.execute(text("SELECT formula_id, formula_name_vi FROM formula WHERE formula_name_vi ILIKE :fname"), {"fname": f"%{f_name}%"})
        f_rows = res.fetchall()
        print(f"'{f_name}':", f_rows)
        for r in f_rows:
            res = conn.execute(text("""
                SELECT fp.principle_id, tp.principle_name_vi 
                FROM formulaprinciple fp 
                JOIN therapeuticprinciple tp ON tp.principle_id = fp.principle_id 
                WHERE fp.formula_id = :fid
            """), {"fid": r[0]})
            print(f"  Principles for {r[1]}:", res.fetchall())
            
    print("\n--- 4. TỲ VỊ HƯ HÀN PATTERN ---")
    res = conn.execute(text("SELECT pattern_id, pattern_name_vi FROM syndromepattern WHERE pattern_name_vi ILIKE '%tỳ vị hư hàn%' OR pattern_name_vi ILIKE '%tỳ dương hư%'"))
    print("Patterns:", res.fetchall())

