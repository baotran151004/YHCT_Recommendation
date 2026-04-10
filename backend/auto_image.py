import time
import requests
from database import SessionLocal
from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class HerbMaterial(Base):
    __tablename__ = "HerbMaterial"
    __table_args__ = {'extend_existing': True}
    
    herb_id = Column(String, primary_key=True)
    herb_name_vi = Column(String)
    herb_name_latin = Column(String)
    image_url = Column(String, nullable=True)

def make_request_with_retry(url, params=None, retries=3):
    headers = {"User-Agent": "YHCT_Bot/6.0_CommonsLatinClean"}
    for i in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code >= 500:
                time.sleep(1)
                continue
            else:
                return None
        except requests.exceptions.RequestException:
            time.sleep(1)
    return None

def filter_commons_result(title):
    title_lower = title.lower()
    
    if "file:" not in title_lower:
        return False
        
    unwanted_keywords = ["person", "portrait", "city", "flag", "building", "map", "logo", "statue", "monument"]
    for word in unwanted_keywords:
        if word in title_lower:
            return False
            
    return True

def clean_latin_name(latin_name):
    """
    Chuẩn hoá tên Latin:
    - Loại bỏ danh từ chỉ bộ phận dùng (Radix, Rhizoma...)
    - Chuyển đuôi sinh cách (Genitive) về danh cách (Nominative) để lấy tên loài chuẩn.
    """
    if not latin_name:
        return ""
        
    # Danh sách các bộ phận dùng thường đứng đầu trong tên YHCT
    parts_to_remove = [
        "radix", "rhizoma", "folium", "cortex", "semen", "fructus", 
        "bulbus", "herba", "caulis", "flos", "ramulus", "lignum", 
        "spica", "pericarpium", "exocarpium", "tuber", "cornu", "colla", "calculus"
    ]
    
    words = latin_name.strip().split()
    cleaned_words = [word for word in words if word.lower() not in parts_to_remove]
    
    if not cleaned_words:
        return ""
        
    first_word = cleaned_words[0]
    
    # Chuẩn hoá nhanh một số đuôi Genitive phổ biến
    stem_map = {
        "Citri": "Citrus",
        "Ligustici": "Ligusticum",
        "Astragali": "Astragalus",
        "Ophiopogonis": "Ophiopogon",
        "Leonuri": "Leonurus",
        "Carthami": "Carthamus",
        "Zingiberis": "Zingiber",
        "Cinnamomi": "Cinnamomum"
    }
    
    if first_word in stem_map:
        cleaned_words[0] = stem_map[first_word]
    elif first_word.endswith("ae"):
        # Ví dụ: Glycyrrhizae -> Glycyrrhiza, Angelicae -> Angelica
        cleaned_words[0] = first_word[:-2] + "a"
        
    # Trả về kết quả sau chuẩn hoá (VD: "Glycyrrhiza" hoặc "Ligusticum wallichii")
    return " ".join(cleaned_words)

def get_image_commons(scientific_name):
    """
    Tìm kiếm và lấy ảnh sử dụng Tên Khoa Học Đã Chuẩn Hoá
    """
    if not scientific_name:
        return None
        
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": scientific_name,
        "gsrnamespace": "6",
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url"
    }
    
    data = make_request_with_retry(url, params=params)
    
    if not data or "query" not in data or "pages" not in data["query"]:
        return None
        
    pages = data["query"]["pages"]
    results = list(pages.values())
    
    for page in results:
        title = page.get("title", "")
        
        if not filter_commons_result(title):
            continue
            
        if "imageinfo" in page and len(page["imageinfo"]) > 0:
            image_url = page["imageinfo"][0].get("url")
            
            if image_url and any(ext in image_url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                return image_url
                
    return None

def main():
    db = SessionLocal()
    missing_images = []
    
    try:
        herbs = db.query(HerbMaterial).all()
        print(f"Tổng số dược liệu trong Database: {len(herbs)}")
        
        count_success = 0
        count_fail = 0
        
        for herb in herbs:
            if herb.image_url:
                print(f"Bỏ qua (đã có ảnh): {herb.herb_name_vi}")
                continue

            if not herb.herb_name_latin:
                count_fail += 1
                print(f"❌ FAIL: (Không có tên Latin) - {herb.herb_name_vi}")
                missing_images.append(f"{herb.herb_id} | TIẾNG VIỆT: {herb.herb_name_vi} | LATIN: NONE")
                continue
                
            # Bước 1: Chuẩn hoá tên 
            scientific_name = clean_latin_name(herb.herb_name_latin)
            
            # Bước 2: Gọi Commons API
            image_url = get_image_commons(scientific_name)
            
            if image_url:
                herb.image_url = image_url
                db.commit()
                count_success += 1
                # In thông báo chuẩn đúng như format yêu cầu chứa dữ liệu gốc 
                print(f"✔ SUCCESS: {herb.herb_name_latin} -> {scientific_name} ({image_url})")
            else:
                count_fail += 1
                # Format ❌ FAIL cho latin_name
                print(f"❌ FAIL: {herb.herb_name_latin} -> {scientific_name}")
                missing_images.append(f"{herb.herb_id} | TIẾNG VIỆT: {herb.herb_name_vi} | GỐC: {herb.herb_name_latin} | TÌM THEO: {scientific_name}")
                
            time.sleep(0.5)
            
        print(f"\n--- TỔNG KẾT ---")
        print(f"Đã cập nhật mới: {count_success} dược liệu")
        print(f"Thất bại: {count_fail} dược liệu")
        
        if missing_images:
            with open("missing_images.txt", "w", encoding="utf-8") as f:
                f.write("Danh sách dược liệu không tìm được ảnh trên Wikimedia Commons:\n")
                f.write("-" * 60 + "\n")
                for item in missing_images:
                    f.write(f"{item}\n")
            print(f"\nĐã ghi {len(missing_images)} dược liệu vào 'missing_images.txt'")
            
    except Exception as e:
        print(f"Có lỗi hệ thống xảy ra: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
