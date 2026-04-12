import sys
import os
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python versions
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Load environment variables
# Load environment variables from the same directory as the script
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

from database import SessionLocal, engine
import models

# 1. Cấu hình ánh xạ cột đặc biệt (CSV / SQL Server export → tên cột trong Model)
COLUMN_MAPPING = {
    "herbmaterial": {
        "herb_name": "herb_name_vi",
    },
    "syndromepattern": {
        "pattern.id": "pattern_id",
    },
    "therapeuticprinciple": {
        "principle.id": "principle_id",
    },
    "patternprinciple": {
        "pattern.id": "pattern_id",
        "principle.id": "principle_id",
    },
    # SSMS: formula_name, object_tcm, function_tcm, usage_tcm; CSV nội bộ: object, function, usage
    "formula": {
        "formula_name": "formula_name_vi",
        "object": "object_tcm",
        "function": "function_tcm",
        "usage": "usage_tcm",
    },
}

# 2. Cấu hình biến thể tên file (Nếu file thực tế khác tên Config)
FILENAME_ALIASES = {
    "syndrome_pattern": ["syndrome_pattern", "syndromepattern"],
}

# 3. Thứ tự Import để đảm bảo Foreign Key
IMPORT_ORDER = [
    {"name": "symptom", "model": models.Symptom, "pk": "symptom_id"},
    {"name": "therapeuticprinciple", "model": models.TherapeuticPrinciple, "pk": "principle_id"},
    {"name": "syndromepattern", "model": models.SyndromePattern, "pk": "pattern_id"},
    {"name": "herbmaterial", "model": models.HerbMaterial, "pk": "herb_id"},
    {"name": "symptomalias", "model": models.SymptomAlias, "pk": None},
    {"name": "patternsymptom", "model": models.PatternSymptom, "pk": ["pattern_id", "symptom_id"]},
    {"name": "patternprinciple", "model": models.PatternPrinciple, "pk": ["pattern_id", "principle_id"]},
    {"name": "formula", "model": models.Formula, "pk": "formula_id"},
    {"name": "formulacomponent", "model": models.FormulaComponent, "pk": None},
    {"name": "formulaprinciple", "model": models.FormulaPrinciple, "pk": ["formula_id", "principle_id"]}
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def normalize_id(value):
    """Đảm bảo ID luôn là chuỗi và không có đuôi .0 nếu là số."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except:
        pass
    
    # Nếu là float hoặc int, chuyển sang str và xóa .0
    if isinstance(value, (float, int)):
        s = str(value)
        if s.endswith('.0'):
            return s[:-2]
        return s
    
    # Nếu là chuỗi, dọn dẹp khoảng trắng
    if isinstance(value, str):
        s = value.strip()
        if s.lower() in ("null", "none", "nan"):
            return None
        return s
    return str(value)


def normalize_cell(value):
    """Chuyển NaN và chuỗi 'null' từ export thành None thật."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in ("null", "none", "nan"):
            return None
        return s
    return value


def get_model_columns(model):
    """Lấy danh sách các cột hợp lệ từ SQLAlchemy Model"""
    return [c.key for c in inspect(model).mapper.column_attrs]

def load_file(base_name):
    """Tìm và đọc file CSV hoặc Excel với Encoding chuẩn Vietnamese"""
    names_to_try = FILENAME_ALIASES.get(base_name, [base_name])
    
    for name in names_to_try:
        csv_path = os.path.join(DATA_DIR, f"{name}.csv")
        xlsx_path = os.path.join(DATA_DIR, f"{name}.xlsx")
        
        # Thử CSV trước
        if os.path.exists(csv_path):
            print(f"Reading CSV: {csv_path}")
            # Dùng utf-8-sig để xử lý BOM từ Excel export
            return pd.read_csv(csv_path, encoding='utf-8-sig')
        # Sau đó thử Excel
        elif os.path.exists(xlsx_path):
            print(f"Reading Excel: {xlsx_path}")
            return pd.read_excel(xlsx_path)
            
    return None


def import_data():
    db: Session = SessionLocal()
    if not os.path.exists(DATA_DIR):
        print(f"Error: Directory {DATA_DIR} not found")
        return

    print("Starting data CLEAN import process (Robust version)...")

    # Optional: Clear tables in reverse order to avoid FK issues
    # Note: We keep "users" and "searchhistory" untouched.
    for item in reversed(IMPORT_ORDER):
        name = item["name"]
        model = item["model"]
        print(f"Clearing table {name}...", end=" ")
        try:
            db.query(model).delete()
            db.commit()
            print("Done.")
        except Exception as e:
            db.rollback()
            print(f"Failed (likely has dependents): {e}")

    for item in IMPORT_ORDER:
        name = item["name"]
        model = item["model"]
        pk = item["pk"]
        
        df = load_file(name)
        if df is None:
            print(f"SKIP {name}: No file {name}.csv / {name}.xlsx in {DATA_DIR}/")
            continue
        if df.empty:
            print(f"SKIP {name}: Empty file")
            continue

        # Ánh xạ cột (Mapping)
        if name in COLUMN_MAPPING:
            df = df.rename(columns=COLUMN_MAPPING[name])
            
        # Lấy các cột hợp lệ của Model
        valid_columns = get_model_columns(model)
        
        df = df.where(pd.notnull(df), None)

        count_new = 0
        count_updated = 0
        count_error = 0
        
        # Pre-fetch existing records for faster access (if PK is simple)
        existing_map = {}
        if pk and not isinstance(pk, list):
            try:
                records = db.query(model).all()
                existing_map = {str(getattr(r, pk)): r for r in records}
            except Exception as e:
                print(f"Warning: Could not pre-fetch records for {name}: {e}")

        total_rows = len(df)
        print(f"Processing {total_rows} rows for {name}...", flush=True)

        for index, row in df.iterrows():
            if index % 50 == 0 and index > 0:
                print(f"  ...progress: {index}/{total_rows}", flush=True)
            
            try:
                raw_data = row.to_dict()

                # Lọc cột theo model + chuẩn hóa null + Normalize IDs
                filtered_data = {}
                for k, v in raw_data.items():
                    if k in valid_columns:
                        if k.endswith("_id") or k == "id" or k == "alias":
                            filtered_data[k] = normalize_id(v)
                        else:
                            filtered_data[k] = normalize_cell(v)
                
                # Kiểm tra trùng lặp và Cập nhật (UPSERT)
                existing_record = None
                if pk:
                    if not isinstance(pk, list):
                        val = str(filtered_data.get(pk))
                        if val in existing_map:
                            existing_record = existing_map[val]
                    else:
                        try:
                            query = db.query(model)
                            for k in pk:
                                query = query.filter(getattr(model, k) == filtered_data[k])
                            existing_record = query.first()
                        except Exception:
                            existing_record = None
                else:
                    # Specialized check for PK-less tables to avoid duplicates when re-running
                    try:
                        query = db.query(model)
                        for k, v in filtered_data.items():
                            if v is not None:
                                query = query.filter(getattr(model, k) == v)
                        existing_record = query.first()
                    except Exception:
                        existing_record = None

                if existing_record:
                    # Cập nhật thông tin cũ (chỉ nếu có thay đổi)
                    changed = False
                    for key, value in filtered_data.items():
                        if getattr(existing_record, key) != value:
                            setattr(existing_record, key, value)
                            changed = True
                    if changed:
                        count_updated += 1
                else:
                    # Thêm mới
                    record = model(**filtered_data)
                    db.add(record)
                    count_new += 1
                    if pk and not isinstance(pk, list):
                        existing_map[str(filtered_data[pk])] = record

            except Exception as e:
                count_error += 1
                if count_error <= 3:
                    print(f"  Row error at {index}: {e}")
            
            # Batch commit every 100 rows
            if (index + 1) % 100 == 0:
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
        
        # FINAL COMMIT FOR THE TABLE
        try:
            db.commit()
            print(f"OK {name}: New {count_new}, Updated {count_updated}, Errors {count_error}", flush=True)
        except Exception as e:
            print(f"Error committing table {name}: {e}")
            db.rollback()

    print("\nMIGRATION PROCESS COMPLETED!")
    db.close()

if __name__ == "__main__":
    import_data()
