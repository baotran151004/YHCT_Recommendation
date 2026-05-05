import os
import sys
os.environ['DATABASE_URL'] = 'postgresql://postgres:riZTueCAvXKxSOVJDfewTUGDdDaosgeZ@interchange.proxy.rlwy.net:49607/railway'
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'd:\\LATN\\yhct_recommentder\\backend')
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("--- 5. ĐÀM THẤP SYMPTOMS ---")
    res = conn.execute(text("SELECT pattern_id, pattern_name_vi, clinical_manifestations FROM syndromepattern WHERE pattern_name_vi ILIKE '%đàm thấp%'"))
    for r in res.fetchall():
        print(f"{r[0]}: {r[1]} -> {r[2]}")
