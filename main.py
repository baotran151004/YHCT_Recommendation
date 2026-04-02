from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal
from sqlalchemy import text
from sentence_transformers import SentenceTransformer, util
import torch

app = FastAPI()

# Cache data patterns directly in memory to keep it fast
knowledge_base = []
model = None

# =========================
# CONCEPT GROUPING (ALIASES)
# =========================
SYMPTOM_EXPANSIONS = {}

def expand_text_with_synonyms(text: str) -> str:
    if not text:
        return ""
    original = text.lower()
    expanded_parts = [original]
    for key, synonyms in SYMPTOM_EXPANSIONS.items():
        if key in original:
            expanded_parts.append(" ".join(synonyms))
    return " ".join(expanded_parts)

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def load_data():
    global knowledge_base, model, SYMPTOM_EXPANSIONS
    try:
        with SessionLocal() as db:
            # 0.5 Tự động nạp từ điển đồng nghĩa từ Database
            print("⏳ Nạp từ điển đồng nghĩa từ bảng SymptomAlias...")
            try:
                res_aliases = db.execute(text("""
                    SELECT s.symptom_name, sa.alias
                    FROM Symptom s
                    JOIN SymptomAlias sa ON s.symptom_id = sa.symptom_id
                """))
                aliases_mapped = [r._mapping for r in res_aliases.fetchall()]
                res_aliases.close()

                SYMPTOM_EXPANSIONS.clear()
                count_aliases = 0
                for row in aliases_mapped:
                    if not row["symptom_name"] or not row["alias"]:
                        continue
                    base_symptom = row["symptom_name"].lower().strip()
                    alias_name = row["alias"].lower().strip()
                    
                    if base_symptom not in SYMPTOM_EXPANSIONS:
                        SYMPTOM_EXPANSIONS[base_symptom] = []
                    if alias_name not in SYMPTOM_EXPANSIONS[base_symptom]:
                        SYMPTOM_EXPANSIONS[base_symptom].append(alias_name)
                        count_aliases += 1
                print(f"✅ Đã nạp {count_aliases} alias cho {len(SYMPTOM_EXPANSIONS)} nhóm triệu chứng cốt lõi.")
            except Exception as e:
                print(f"⚠️ Lỗi khi nạp từ điển đồng nghĩa: {e}")

            # 0. Tải Model AI
            print("⏳ Loading Vector Embedding Model... (paraphrase-multilingual-MiniLM-L12-v2)")
            # Sử dụng CPU mặc định trên production server, hoặc CUDA nếu có card rời
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)
            print(f"✅ AI Model loaded successfully on {device}")

            # 1. Tải bài thuốc & Thành phần (In-memory Join)
            print("⏳ Đang nạp và hợp nhất dữ liệu Bài thuốc...")
            
            # A. Tải danh sách bài thuốc
            res_formulas = db.execute(text("SELECT * FROM [Formula]"))
            formulas_mapped = [r._mapping for r in res_formulas.fetchall()]
            res_formulas.close()

            # B. Tải thông tin Thảo dược
            res_herbs = db.execute(text("SELECT herb_id, herb_name_vi FROM [HerbMaterial]"))
            herbs_dict = {h._mapping["herb_id"]: h._mapping["herb_name_vi"] for h in res_herbs.fetchall()}
            res_herbs.close()

            # C. Tải liên kết Bài thuốc - Thảo dược
            res_fc = db.execute(text("SELECT * FROM [FormulaComponent]"))
            fc_rows = [r._mapping for r in res_fc.fetchall()]
            res_fc.close()

            # Group ingredients by formula_id
            comp_by_fid = {}
            for fc in fc_rows:
                fid = fc["formula_id"]
                hid = fc["herb_id"]
                name = herbs_dict.get(hid, "N/A")
                dosage = fc.get("dosage_value")
                unit = fc.get("dosage_unit", "")
                note = fc.get("dosage_note")
                
                ingredient_obj = {
                    "name": name,
                    "dosage": dosage,
                    "unit": unit,
                    "note": note
                }
                
                if fid not in comp_by_fid:
                    comp_by_fid[fid] = []
                comp_by_fid[fid].append(ingredient_obj)

            # Build final knowledge_base mapping
            formulas_dict = {}
            for f in formulas_mapped:
                fid = f["formula_id"]
                ind_text = f["indications"] or ""
                
                # STORE AS LIST FOR GRID DISPLAY
                ingredients = comp_by_fid.get(fid, [])

                formulas_dict[fid] = {
                    "name": f["formula_name_vi"],
                    "category": f.get("formula_category", "N/A"),
                    "indications": ind_text,
                    "composition": ingredients,
                    "usage": f.get("usage_tcm") or "Đang cập nhật...",
                    "search_indications": expand_text_with_synonyms(ind_text),
                    "search_manifestations": ""
                }

            # 2. Bổ sung thêm triệu chứng từ thể bệnh (SyndromePattern) để search rộng hơn
            print("⏳ Đang nạp ánh xạ triệu chứng từ Thể bệnh...")
            res_mappings = db.execute(text("""
                SELECT f.formula_id, sp.clinical_manifestations
                FROM Formula f
                JOIN FormulaPrinciple fp ON f.formula_id = fp.formula_id
                JOIN PatternPrinciple pp ON pp.principle_id = fp.principle_id
                JOIN SyndromePattern sp ON sp.pattern_id = pp.pattern_id
            """))
            mappings_mapped = [r._mapping for r in res_mappings.fetchall()]
            res_mappings.close()

            manifestations_by_formula = {}
            for m in mappings_mapped:
                mid = m["formula_id"]
                m_man = m["clinical_manifestations"]
                if m_man:
                    if mid not in manifestations_by_formula:
                        manifestations_by_formula[mid] = set()
                    for man in m_man.split(","):
                        manifestations_by_formula[mid].add(man.strip().lower())
                        
            for fid, man_set in manifestations_by_formula.items():
                if fid in formulas_dict:
                    unique_man_str = ", ".join(man_set)
                    formulas_dict[fid]["search_manifestations"] = expand_text_with_synonyms(unique_man_str)

            # 3. Tính toán Vector Embeddings (Chỉ 1 lần khi startup)
            print("⏳ Computing vector embeddings for the knowledge base...")
            for fid, fdata in formulas_dict.items():
                s_ind = fdata["search_indications"].strip()
                s_man = fdata["search_manifestations"].strip()
                
                # Optimize by caching vectors into standard dictionary
                fdata["indications_emb"] = model.encode(s_ind, convert_to_tensor=True) if s_ind else None
                fdata["manifestations_emb"] = model.encode(s_man, convert_to_tensor=True) if s_man else None

            global knowledge_base
            knowledge_base = list(formulas_dict.values())
            print(f"✅ EXPERT SYSTEM KNOWLEDGE BASE LOADED: {len(knowledge_base)} formulas")
    except Exception as e:
        print(f"❌ CRITICAL ERROR DURING STARTUP: {e}")
        import traceback
        traceback.print_exc()


# =========================
# HARD FILTER RULES (CHỐNG CHỈ ĐỊNH)
# =========================
CONTRAINDICATIONS_RULES = [
    {
        "keywords": ["nóng lạnh", "sốt cao", "sợ gió", "sợ lạnh", "đờm xanh", "đờm vàng", "ho suyễn cấp", "phát sốt"], 
        "blocked_categories": ["thuốc bổ", "thuốc cố sáp"],
        "reason": "⛔ Có biểu hiện Thực chứng / Biểu chứng cấp tính (tà khí đang thịnh). Tuyệt đối KHÔNG DÙNG THUỐC BỔ hoặc cố sáp để tránh tình trạng 'đóng cửa nhốt giặc' (Lưu tà)."
    },
    {
         "keywords": ["chân tay lạnh", "sợ lạnh", "tiểu trong dài", "tiêu chảy", "phân lỏng"],
         "blocked_categories": ["thuốc thanh nhiệt", "thuốc giải biểu tân lương"],
         "reason": "⛔ Có dấu hiệu Hàn chứng, Dương hư. CHỐNG CHỈ ĐỊNH dùng Thuốc Thanh nhiệt (thuốc hàn lương) vì sẽ làm tổn thương Dương khí, khiến bệnh nặng thêm."
    }
]

# =========================
# CLINICAL WARNINGS DICTIONARY
# =========================
CLINICAL_WARNINGS_RULES = {
    "dehydration": {
        "keywords": ["khô môi", "chóng mặt", "háo nước", "khát nước", "mất nước", "mắt trũng", "tiểu ít"],
        "warning": "Bệnh nhân có yếu tố suy giảm tân dịch. Yêu cầu kết hợp bù nước, điện giải (Oresol) hoặc can thiệp y tế tích cực song song với dùng bài thuốc."
    },
    "high_fever": {
        "keywords": ["sốt cao", "co giật", "mê sảng"],
        "warning": "Triệu chứng sốt cao khẩn cấp. Cần theo dõi sát nhiệt độ và dùng thuốc hạ sốt Tây y, đề phòng co giật trước khi điều trị YHCT."
    },
    "blood_loss": {
        "keywords": ["ngất xỉu", "da xanh tái", "khó thở dữ dội"],
        "warning": "Dấu hiệu suy tuần hoàn hô hấp nghiêm trọng. Cần ưu tiên các biện pháp hồi sức cấp cứu y tế hiện đại khẩn cấp."
    }
}

# =========================
# EXPERT SYSTEM INFERENCE API
# =========================
@app.get("/expert-system/recommend")
def expert_system_inference(symptom: str):
    print("INPUT:", symptom)

    # 1. Tách chuỗi triệu chứng qua dấu phẩy
    # Ví dụ: "Cảm lạnh, có cơn hen phế quản, ho" -> ["cảm lạnh", "có cơn hen phế quản", "ho"]
    input_symptoms = [s.strip().lower() for s in symptom.split(",") if s.strip()]

    if not input_symptoms:
        return []

    # Encode tất cả triệu chứng đầu vào một lượt thành tensor
    input_embeddings = model.encode(input_symptoms, convert_to_tensor=True)

    # LỌC CHỐNG CHỈ ĐỊNH TỪ TRIỆU CHỨNG ĐẦU VÀO
    blocked_categories_for_patient = set()
    blocking_reasons = set()
    
    for isym in input_symptoms:
        for rule in CONTRAINDICATIONS_RULES:
            if any(kw in isym for kw in rule["keywords"]):
                for b_cat in rule["blocked_categories"]:
                    blocked_categories_for_patient.add(b_cat.lower())
                blocking_reasons.add(rule["reason"])

    # 2. Quét cơ sở liệu, tính điểm các BÀI THUỐC
    best_formula = None
    max_score = 0
    best_matched_symptoms = []
    
    SEMANTIC_THRESHOLD = 0.65 # Ngưỡng để Semantic tính điểm phụ trợ

    for formula in knowledge_base:
        f_cat = formula.get("category", "").lower()
        if any(b_cat in f_cat for b_cat in blocked_categories_for_patient):
            continue # ⛔ BỎ QUA - Bị chặn bởi quy tắc gác cổng (Hard Filter)

        score = 0
        search_indications = formula.get("search_indications", "")
        search_manifestations = formula.get("search_manifestations", "")
        ind_emb = formula.get("indications_emb")
        man_emb = formula.get("manifestations_emb")
        matched = []
        
        for i, isym in enumerate(input_symptoms):
            isym_emb = input_embeddings[i]
            sym_score = 0
            is_matched_ui = False
            
            # Khai phá tất cả các từ đồng nghĩa của triệu chứng đầu vào
            isym_variants = [isym]
            for base, aliases in SYMPTOM_EXPANSIONS.items():
                if isym == base or isym in aliases:
                    if base not in isym_variants: isym_variants.append(base)
                    for a in aliases:
                        if a not in isym_variants: isym_variants.append(a)
                        
            # VÒNG 1: EXACT LEXICAL MATCH & SYNONYM (Trọng số Cao nhất)
            # Thêm khoảng trắng để tránh khớp nhầm âm tiết (Ví dụ 'ho' khớp nhầm trong 'hoảng sợ')
            s_ind_padded = f" {search_indications} "
            s_man_padded = f" {search_manifestations} "
            
            if any(f" {variant} " in s_ind_padded for variant in isym_variants):
                sym_score += 50
                is_matched_ui = True
            elif any(f" {variant} " in s_man_padded for variant in isym_variants):
                sym_score += 10
                is_matched_ui = True
                
            # VÒNG 2: FUZZY KEYWORD MATCH (Trọng số Vừa phải)
            if not is_matched_ui:
                words = [w for w in isym.split() if w]
                if len(words) >= 2:
                    overlap_ind = sum(1 for w in words if w in search_indications)
                    overlap_man = sum(1 for w in words if w in search_manifestations)
                    
                    if overlap_ind / len(words) >= 0.7:
                        sym_score += 5
                        is_matched_ui = True
                    elif overlap_man / len(words) >= 0.7:
                        sym_score += 2
                        is_matched_ui = True
                        
            # VÒNG 3: SEMANTIC VECTOR MATCH (Break-tie phụ trợ)
            if not is_matched_ui:
                sim_ind = util.cos_sim(isym_emb, ind_emb).item() if ind_emb is not None else 0.0
                sim_man = util.cos_sim(isym_emb, man_emb).item() if man_emb is not None else 0.0
                
                if sim_ind >= SEMANTIC_THRESHOLD:
                    sym_score += 1
                elif sim_man >= SEMANTIC_THRESHOLD:
                    sym_score += 0.5
                
            if sym_score > 0:
                score += sym_score
            if is_matched_ui:
                matched.append(isym)
                
        # Ưu tiên bài thuốc có điểm cao nhất
        # Nếu bằng điểm, ưu tiên bài có số lượng triệu chứng khớp nhiều hơn
        if score > max_score or (score == max_score and score > 0 and len(matched) > len(best_matched_symptoms)):
            max_score = score
            best_formula = formula
            best_matched_symptoms = matched

    # 3. Quản lý việc không tìm thấy
    if not best_formula or max_score == 0:
        return []

    # 4. Tính toán độ tin cậy của gợi ý
    confidence = round((len(best_matched_symptoms) / len(input_symptoms)) * 100, 2)

    # 5. Phân tích các triệu chứng chưa được giải quyết (Unmatched symptoms)
    unmatched_symptoms = [sym for sym in input_symptoms if sym not in best_matched_symptoms]
    
    # 6. Gợi ý thêm Cảnh báo Lâm sàng (Clinical Warnings)
    clinical_warnings = list(blocking_reasons) # Ưu tiên chèn các lý do cấm thuốc trước
    
    if unmatched_symptoms:
        for rule_key, rule_data in CLINICAL_WARNINGS_RULES.items():
            for kw in rule_data["keywords"]:
                if any(kw in usym for usym in unmatched_symptoms):
                    if rule_data["warning"] not in clinical_warnings:
                        clinical_warnings.append(rule_data["warning"])
                    break

    # Trả về kết quả hoàn hảo
    return [{
        "name": best_formula["name"],
        "category": best_formula["category"],
        "indications": best_formula["indications"],
        "composition": best_formula["composition"],
        "usage": best_formula["usage"],
        "score": max_score,
        "confidence": f"{confidence}%",
        "matched_symptoms": best_matched_symptoms,
        "unmatched_symptoms": unmatched_symptoms,
        "clinical_warnings": clinical_warnings,
        "system_architecture": "Knowledge-based System with Weighted Scoring & Rule-based Clinical Warnings"
    }]