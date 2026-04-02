from database import SessionLocal
from sqlalchemy import text
import sys

try:
    print("Checking Formula table columns...")
    db = SessionLocal()
    # Query to get column names in SQL Server
    res = db.execute(text("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Formula'
    """))
    columns = [row[0] for row in res.fetchall()]
    print("Actual columns in Formula table:")
    print(columns)
    
    # Also check if the table actually has data
    res2 = db.execute(text("SELECT TOP 1 * FROM Formula"))
    print("\nKeys from SELECT *:")
    print(res2.keys())
    
    db.close()
except Exception as e:
    print("\nERROR:")
    print(e)
    sys.exit(1)
