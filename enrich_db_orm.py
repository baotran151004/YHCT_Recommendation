from sqlalchemy import create_engine, MetaData, Table, update
from database import DATABASE_URL
import sys

# CLINICAL DATA FOR COMMON FORMULAS
FORMULA_DATA = {
    "F001": (
        "Ma hoàng 9g, Quế chi 6g, Hạnh nhân 9g, Cam thảo 3g.",
        "Sắc với 600ml nước còn 200ml, chia làm 2 lần uống nóng. Sau khi uống đắp chăn cho ra mồ hôi nhẹ."
    ),
    "F002": (
        "Quế chi 9g, Bạch thược 9g, Sinh khương 9g, Đại táo 12g, Cam thảo 6g.",
        "Sắc uống. Sau khi uống nên ăn cháo nóng và đắp chăn ấm để hỗ trợ ra mồ hôi."
    ),
    "F003": (
        "Khương hoạt 6g, Phòng phong 6g, Thương truật 6g, Tế tân 2g, Xuyên khung 3g, Bạch chỉ 3g, Sinh địa 3g, Hoàng cầm 3g, Cam thảo 2g.",
        "Sắc uống nóng. Có tác dụng giải biểu, trừ thấp, thanh nhiệt."
    ),
    "F004": (
        "Cúc hoa 4g, Tang diệp 10g, Hạnh nhân 8g, Liên kiều 6g, Cát cánh 8g, Bạc hà 3g, Cam thảo 3g, Lô căn 8g.",
        "Sắc uống ngày một thang. Dùng cho chứng cảm mạo phong nhiệt nhẹ (Tang cúc ẩm)."
    ),
    "F005": (
        "Kim ngân hoa 12g, Liên kiều 12g, Kinh giới tuệ 4g, Đạm đậu xị 8g, Cát cánh 8g, Ngưu bàng tử 8g, Bạc hà 4g, Trúc diệp 4g, Cam thảo 4g.",
        "Sắc uống. Tác dụng thanh nhiệt giải độc, thấu biểu phát hãn (Ngân kiều tán)."
    ),
    "F020": (
        "Thừa khí thang: Đại hoàng 12g, Hậu phác 15g, Chỉ thực 12g, Mang tiêu 10g.",
        "Sắc Hậu phác và Chỉ thực trước, sau đó cho Đại hoàng vào sắc sau, cuối cùng hòa Mang tiêu vào uống nóng."
    ),
    "F051": (
        "Tứ vật thang: Thục địa 12-20g, Đương quy 12g, Bạch thược 12g, Xuyên khung 6-8g.",
        "Sắc uống hoặc làm thuốc hoàn. Tác dụng bổ huyết điều kinh."
    ),
    "F052": (
        "Tứ quân tử thang: Nhân sâm 12g, Bạch truật 12g, Phục linh 12g, Cam thảo 4-6g.",
        "Sắc uống hoặc tán bột. Tác dụng ích khí kiện tỳ."
    )
}

def enrich_data():
    try:
        engine = create_engine(DATABASE_URL)
        metadata = MetaData()
        print("⏳ Reflecting Formula table metadata...")
        
        # This will discovery the REAL column names and types automatically
        formula_table = Table('Formula', metadata, autoload_with=engine)
        
        print(f"✅ Found columns: {[c.name for c in formula_table.columns]}")
        
        with engine.begin() as conn:
            for fid, (comp, usage) in FORMULA_DATA.items():
                print(f"⏳ Updating {fid}...")
                stmt = (
                    update(formula_table)
                    .where(formula_table.c.formula_id == fid)
                    .values(composition_tcm=comp, usage_tcm=usage)
                )
                conn.execute(stmt)
                print(f"✅ Updated {fid}")
                
        print("\n🎉 DATA ENRICHMENT COMPLETED!")
    except Exception as e:
        print(f"\n❌ ERROR DURING ENRICHMENT: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    enrich_data()
