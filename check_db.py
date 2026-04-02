from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT TOP 1 * FROM SymptomAlias"))
print("SymptomAlias keys:", res.keys())
res.close()

res2 = db.execute(text("SELECT TOP 1 * FROM Symptom"))
print("Symptom keys:", res2.keys())
res2.close()
