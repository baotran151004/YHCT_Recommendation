from database import SessionLocal
from sqlalchemy import text
import sys

def check_structure():
    try:
        db = SessionLocal()
        print("Checking tables in database...")
        res = db.execute(text("SELECT name FROM sys.tables"))
        tables = [r[0] for r in res.fetchall()]
        print(f"Tables: {tables}")
        
        for table in tables:
            if 'Formula' in table or 'Comp' in table or 'Ingred' in table:
                print(f"\nStructure of {table}:")
                try:
                    res_cols = db.execute(text(f"SELECT TOP 0 * FROM [{table}]"))
                    print(f"Columns: {res_cols.keys()}")
                    
                    res_data = db.execute(text(f"SELECT TOP 1 * FROM [{table}]"))
                    row = res_data.fetchone()
                    if row:
                        print(f"Sample data: {row}")
                    else:
                        print("Table is empty.")
                except Exception as e:
                    print(f"Error checking {table}: {e}")
                    
        db.close()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    check_structure()
