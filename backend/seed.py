from sqlalchemy.orm import Session
from models import Symptom
import uuid

def seed_data(db: Session):
    print("🚀 [db-seed] Checking for initial data...")
    
    # Kiểm tra nếu bảng Symptom rỗng
    symptom_count = db.query(Symptom).count()
    if symptom_count == 0:
        print("🌱 [db-seed] Symptom table is empty. Seeding sample data...")
        
        sample_symptoms = [
            "đau đầu", 
            "sốt", 
            "ho", 
            "tiêu chảy", 
            "buồn nôn"
        ]
        
        for name in sample_symptoms:
            new_symptom = Symptom(
                symptom_id=str(uuid.uuid4())[:8], # Dùng 8 ký tự đầu của UUID cho gọn làm ID mẫu
                symptom_name=name
            )
            db.add(new_symptom)
        
        try:
            db.commit()
            print(f"✅ [db-seed] Seeded {len(sample_symptoms)} symptoms successfully.")
        except Exception as e:
            db.rollback()
            print(f"❌ [db-seed] Error seeding data: {e}")
    else:
        print(f"ℹ️ [db-seed] Symptom table already has {symptom_count} records. Skipping seed.")
