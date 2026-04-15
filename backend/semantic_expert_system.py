import re
import unicodedata
from collections import defaultdict
from typing import Any, List, Dict, Optional

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Hybrid System Constants
EXACT_MATCH_POINTS = 2.0
ALIAS_MATCH_POINTS = 1.5
W_KEYWORD = 1.0
W_SEMANTIC = 0.5
W_COVERAGE = 2.0
W_CONSISTENCY = 1.5
MISMATCH_PENALTY_WEIGHT = 1.0
CONFLICT_PENALTY_VALUE = 5.0
MIN_COVERAGE_THRESHOLD = 0.3  # Hard Rule 1
SOFT_COVERAGE_THRESHOLD = 0.5 # Hard Rule 2

CONFLICT_TAGS = {
    "han": ["nhiet"],
    "nhiet": ["han"],
    "hu": ["thuc"],
    "thuc": ["hu"]
}

CANONICAL_AXIS_RULES = {
    "han": ["so lanh", "lanh", "chan tay lanh", "dom trang", "tieu trong", "thich am", "phan long", "tieu long"],
    "nhiet": ["sot", "sot cao", "khat", "hong do", "dom vang", "mieng kho", "tieu vang", "nong", "phan tao", "tieu do"],
    "hu": ["met moi", "yeu", "hut hoi", "lau ngay", "man tinh", "mo hoi trom", "mat nuoc", "da xanh", "gay yeu"],
    "thuc": ["moi bi", "cap tinh", "dot ngot", "dau du doi", "day tuc", "dom nhieu", "bung truong", "tieu chay", "non oi", "nong lanh", "nhuc dau", "phat sot"],
}

PATTERN_TAG_KEYWORDS = {
    "han": ["han", "lanh", "tu han", "hong nhuan", "bach dam"],
    "nhiet": ["nhiet", "nong", "thanh nhiet", "hoa hoa", "dom vang", "hong do"],
    "hu": ["hu", "khi hu", "huyet hu", "am hu", "duong hu", "suy"],
    "thuc": ["thuc", "uat", "tre", "be tac", "truong man", "ta thinh"],
}

SYMPTOM_PROPERTY_KEYWORDS = {
    "heat": ["khô", "sốt", "khát", "ho khan", "nóng", "đỏ", "vàng", "táo bón", "nhiệt", "mồ hôi nhiều"],
    "cold": ["sợ lạnh", "ớn lạnh", "không ra mồ hôi", "lạnh", "trắng", "tiêu lỏng", "hàn", "nhạt", "rét"]
}

def normalize_text(value: str, remove_accents: bool = False) -> str:
    """Normalize Vietnamese text for consistent matching."""
    if not value:
        return ""
    lowered = value.lower().strip()
    
    if remove_accents:
        normalized = unicodedata.normalize("NFKD", lowered)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.replace("đ", "d")
        normalized = re.sub(r"[^a-z0-9\s,;/+-]", " ", normalized)
    else:
        normalized = unicodedata.normalize("NFC", lowered)
        normalized = re.sub(r"[^\w\s,;/+-]", " ", normalized)
    
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

def split_input_parts(symptom_text: str) -> list[str]:
    """Split input into individual symptoms based on separators."""
    if not symptom_text:
        return []
    # Split by common separators
    parts = [p.strip() for p in re.split(r"[,;\n.]+", symptom_text) if p.strip()]
    if len(parts) > 1:
        return parts
    
    # Fallback: check for "va", "kem", "kiem"
    norm = normalize_text(symptom_text)
    parts = [p.strip() for p in re.split(r"\bva\b|\bkem\b|\bkiem\b", norm) if p.strip()]
    return parts if parts else [symptom_text.strip()]

class SemanticExpertSystemEngine:
    """
    Rule-based Expert System for TCM Recommendation.
    Uses a point-based scoring system and conflict resolution logic.
    """
    def __init__(self):
        self.ready = False
        self.symptoms: Dict[str, Dict[str, Any]] = {}  # id -> {id, name, norm_name}
        self.alias_map: Dict[str, str] = {}           # norm_alias -> symptom_id
        self.patterns: Dict[str, Dict[str, Any]] = {}  # id -> {id, name, manifestations, tags, symptom_weights}
        self.formulas: Dict[str, Dict[str, Any]] = {}  # id -> {id, name, indications, explanation, etc}
        self.pattern_principles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.principle_formulas: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.formula_components: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.pattern_symptom_source = "uninitialized"

    def load(self, session_factory) -> None:
        """Load knowledge base from database."""
        with session_factory() as db:
            self._load_data(db)
            
            # Fallback: if no pattern-symptom links exist, derive them from manifestation text
            has_links = any(p["symptom_weights"] for p in self.patterns.values())
            if not has_links:
                print("[expert-system] No links found in DB. Deriving from manifestations text...")
                self._derive_links_from_text()
        
        # Readiness check: Symptoms, Patterns, and Formulas must exist
        self.ready = bool(self.symptoms and self.patterns and self.formulas)
        if not self.ready:
            print("[expert-system] Warning: Knowledge base is empty or incomplete.")
        else:
            print(f"[expert-system] Ready: {len(self.symptoms)} symptoms, {len(self.formulas)} formulas.")

    def _derive_links_from_text(self):
        """Rule-based derivation: link symptoms if their names appear in pattern manifests."""
        self.pattern_symptom_source = "derived_keywords"
        count = 0
        for pid, pattern in self.patterns.items():
            manifest = normalize_text(pattern["manifestations"])
            manifest_plain = normalize_text(pattern["manifestations"], remove_accents=True)
            if not manifest: continue
            
            for sid, symptom in self.symptoms.items():
                s_norm = symptom["norm"]
                s_plain = normalize_text(symptom["name"], remove_accents=True)
                
                # Match accented or plain versions
                if s_norm in manifest or s_plain in manifest_plain:
                    pattern["symptom_weights"][sid] = 1.0
                    count += 1
        logger.info(f"[EXPERT-SYSTEM] Derived {count} links using keyword matching.")
        # Re-check readiness after derivation
        self.ready = bool(self.symptoms and self.patterns and self.formulas)

    def _query_rows(self, db, sql: str, params: Optional[dict] = None) -> List[dict]:
        result = db.execute(text(sql), params or {})
        rows = [dict(row._mapping) for row in result.fetchall()]
        result.close()
        # Case-insensitive normalization for PostgreSQL metadata consistency
        return [{k.lower(): v for k, v in r.items()} for r in rows]

    def _load_data(self, db):
        # 1. Symptoms & Aliases
        raw_symptoms = self._query_rows(db, "SELECT symptom_id, symptom_name FROM symptom")
        for row in raw_symptoms:
            sid = str(row["symptom_id"])
            name = str(row["symptom_name"])
            self.symptoms[sid] = {"id": sid, "name": name, "norm": normalize_text(name)}
            
            # Populate alias map with both versions
            self.alias_map[normalize_text(name)] = sid
            self.alias_map[normalize_text(name, remove_accents=True)] = sid
        
        raw_aliases = self._query_rows(db, "SELECT symptom_id, alias FROM symptomalias")
        for row in raw_aliases:
            sid = str(row["symptom_id"])
            alias = str(row["alias"])
            self.alias_map[normalize_text(alias)] = sid
            self.alias_map[normalize_text(alias, remove_accents=True)] = sid

        # 2. Patterns
        raw_patterns = self._query_rows(db, "SELECT pattern_id, pattern_name_vi, clinical_manifestations FROM syndromepattern")
        for row in raw_patterns:
            pid = str(row["pattern_id"])
            name = str(row["pattern_name_vi"])
            manifest = str(row["clinical_manifestations"] or "")
            self.patterns[pid] = {
                "id": pid,
                "name": name,
                "manifestations": manifest,
                "tags": self._infer_tags(name + " " + manifest),
                "symptom_weights": {}
            }

        # 3. Pattern-Symptom Links
        raw_links = self._query_rows(db, """
            SELECT pattern_id, symptom_id, weight 
            FROM patternsymptom 
            UNION
            SELECT pattern_id, symptom_id, 1 as weight 
            FROM patternsymptom 
            WHERE 1=0 -- fallback just in case
        """)
        for row in raw_links:
            pid, sid = str(row["pattern_id"]), str(row["symptom_id"])
            if pid in self.patterns:
                self.patterns[pid]["symptom_weights"][sid] = float(row.get("weight") or 1.0)

        # 4. Principles & Formulas
        raw_formulas = self._query_rows(db, "SELECT formula_id, formula_name_vi, function_tcm, indications FROM formula")
        for row in raw_formulas:
            fid = str(row["formula_id"])
            self.formulas[fid] = {
                "id": fid,
                "name": row["formula_name_vi"],
                "phep_tri": row["function_tcm"] or "Chưa rõ",
                "indications": row["indications"]
            }

        # 5. Principles per Pattern
        raw_principles = self._query_rows(db, """
            SELECT pp.pattern_id, tp.principle_name_vi, tp.principle_id
            FROM patternprinciple pp
            JOIN therapeuticprinciple tp ON tp.principle_id = pp.principle_id
        """)
        for row in raw_principles:
            self.pattern_principles[str(row["pattern_id"])].append({
                "id": str(row["principle_id"]),
                "name": row["principle_name_vi"]
            })

        # 6. Formulas per Principle
        raw_fp = self._query_rows(db, "SELECT principle_id, formula_id FROM formulaprinciple")
        for row in raw_fp:
            fid = str(row["formula_id"])
            if fid in self.formulas:
                self.principle_formulas[str(row["principle_id"])].append(self.formulas[fid])

        # 7. Formula Components
        raw_components = self._query_rows(db, """
            SELECT fc.formula_id, hm.herb_name_vi, hm.image_url, fc.dosage_value, fc.dosage_unit, fc.dosage_note
            FROM formulacomponent fc
            JOIN herbmaterial hm ON hm.herb_id = fc.herb_id
        """)
        for row in raw_components:
            self.formula_components[str(row["formula_id"])].append({
                "name": row["herb_name_vi"],
                "image": row["image_url"],
                "dosage": row["dosage_value"],
                "unit": row["dosage_unit"],
                "note": row["dosage_note"]
            })

    def _infer_tags(self, text: str) -> set:
        tags = set()
        norm_text = normalize_text(text)
        for tag, keywords in PATTERN_TAG_KEYWORDS.items():
            if any(k in norm_text for k in keywords):
                tags.add(tag)
        return tags

    def _infer_symptom_nature(self, name: str) -> str:
        norm_name = normalize_text(name, remove_accents=False).lower()
        norm_plain = normalize_text(name, remove_accents=True).lower()
        
        for kw in SYMPTOM_PROPERTY_KEYWORDS["heat"]:
            if kw in norm_name or normalize_text(kw, remove_accents=True) in norm_plain:
                return "heat"
        for kw in SYMPTOM_PROPERTY_KEYWORDS["cold"]:
            if kw in norm_name or normalize_text(kw, remove_accents=True) in norm_plain:
                return "cold"
        return "neutral"

    def recommend(self, input_text: str, top_k: int = 1) -> List[dict]:
        """
        Main entry point for recommendation.
        Calculates scores for patterns based on input symptoms and conflicts.
        """
        if not self.ready:
            return []
        
        # 1. Tokenize and Match Symptoms
        input_parts = split_input_parts(input_text)
        matched_symptoms = [] # List of {id, name, score, original, method}
        ignored_symptoms = [] # List of parts that did not match anything
        detected_user_tags = set()
        normalized_symptoms_for_ui = []

        logger.info(f"[INTERNAL-MATCH] Processing input: '{input_text}'")

        for part in input_parts:
            # Try matching with accents first, then without
            norm_accent = normalize_text(part)
            norm_plain = normalize_text(part, remove_accents=True)
            
            sid = None
            method = "none"
            is_exact = False
            
            if norm_accent in self.alias_map:
                sid = self.alias_map[norm_accent]
                is_exact = (self.symptoms[sid]["norm"] == norm_accent)
                method = "exact" if is_exact else "alias"
            elif norm_plain in self.alias_map:
                sid = self.alias_map[norm_plain]
                method = "alias-plain"
            
            if sid:
                score = EXACT_MATCH_POINTS if is_exact else ALIAS_MATCH_POINTS
                match_info = {
                    "id": str(sid), 
                    "name": str(self.symptoms[sid]["name"]),
                    "score": score, 
                    "original": str(part),
                    "method": method
                }
                matched_symptoms.append(match_info)
                normalized_symptoms_for_ui.append({
                    "symptom_id": str(sid),
                    "symptom_name": str(self.symptoms[sid]["name"]),
                    "alias_used": str(part) if method != "exact" else "None",
                    "match_method": method,
                    "confidence": 1.0 if is_exact else 0.9,
                    "raw_inputs": [str(part)]
                })
                logger.info(f"[INTERNAL-MATCH] Found match: '{part}' -> {self.symptoms[sid]['name']} via {method}")
            else:
                # b. Partial match (keyword search) fallback
                is_fallback_matched = False
                for fallback_sid, data in self.symptoms.items():
                    if data["norm"] in norm_accent or norm_accent in data["norm"]:
                        match_info = {
                            "id": str(fallback_sid), 
                            "name": str(data["name"]),
                            "score": ALIAS_MATCH_POINTS, 
                            "original": str(part),
                            "method": "contains"
                        }
                        matched_symptoms.append(match_info)
                        normalized_symptoms_for_ui.append({
                            "symptom_id": str(fallback_sid),
                            "symptom_name": str(data["name"]),
                            "alias_used": "Keyword match",
                            "match_method": "contains",
                            "confidence": 0.8,
                            "raw_inputs": [str(part)]
                        })
                        logger.info(f"[INTERNAL-MATCH] Found keyword match: '{part}' -> {data['name']}")
                        is_fallback_matched = True
                        break
                
                if not is_fallback_matched:
                    ignored_symptoms.append(str(part))
                    logger.info(f"[INTERNAL-MATCH] Ignored invalid symptom: '{part}'")
            
            # Detect patient tags (han, nhiet, etc)
            for tag, keywords in CANONICAL_AXIS_RULES.items():
                if any(k in norm_accent for k in keywords):
                    detected_user_tags.add(tag)

        if not matched_symptoms:
            logger.info("[INTERNAL-MATCH] No symptoms matched.")
            return []

        valid_input_count = len(matched_symptoms)
        if valid_input_count == 0:
            logger.info("[INTERNAL-MATCH] No valid symptoms to score.")
            return []

        # 2. Score All Patterns and find Candidates (Hybrid Approach)
        all_pattern_results = []
        for pid, pattern in self.patterns.items():
            pattern_matches = [m for m in matched_symptoms if m["id"] in pattern["symptom_weights"]]
            matched_count = len(pattern_matches)
            if matched_count == 0:
                continue
            
            # a. Symptom Coverage (Weighted Coverage)
            # Fetch weights directly from the DB's pattern-symptom relation
            matched_weight = sum(pattern["symptom_weights"][m["id"]] for m in pattern_matches)
            unmatched_count = valid_input_count - matched_count
            input_total_weight = matched_weight + (unmatched_count * 1.0) # Unmatched valid ones have weight 1.0
            
            coverage = matched_weight / input_total_weight if input_total_weight > 0 else 0
            
            # Hard Rule 1: Drop completely if coverage < 0.3
            if coverage < MIN_COVERAGE_THRESHOLD:
                continue

            # b. Keyword vs Semantic Scores
            keyword_score = sum([m["score"] for m in pattern_matches if m["method"] == "exact"])
            semantic_score = sum([m["score"] for m in pattern_matches if m["method"] != "exact"])
            
            # c. Pattern Consistency
            consistency_ratio = matched_count / valid_input_count
            consistency_bonus = consistency_ratio * 2.0  # max 2.0
            
            # d. Mismatch & Conflict Penalty
            penalty = 0.0
            penalty += unmatched_count * MISMATCH_PENALTY_WEIGHT
            
            has_conflict = False
            for tag, conflicts in CONFLICT_TAGS.items():
                if tag in detected_user_tags:
                    if any(c in detected_user_tags for c in conflicts):
                        has_conflict = True
                    if any(c in pattern["tags"] for c in conflicts):
                        has_conflict = True
                        
            if has_conflict:
                penalty += CONFLICT_PENALTY_VALUE
                
            # Syndrome Property Layer (Heat/Cold)
            heat_score = 0.0
            cold_score = 0.0
            for m in pattern_matches:
                nature = self._infer_symptom_nature(m["name"])
                weight = pattern["symptom_weights"][m["id"]]
                if nature == "heat":
                    heat_score += weight
                elif nature == "cold":
                    cold_score += weight
                    
            property_bonus = 0.0
            if heat_score > cold_score:
                if "nhiet" in pattern["tags"]: property_bonus += 2.0
                if "han" in pattern["tags"]: property_bonus -= 3.0
            elif cold_score > heat_score:
                if "han" in pattern["tags"]: property_bonus += 2.0
                if "nhiet" in pattern["tags"]: property_bonus -= 3.0
                
            # e. Calculate Final Score
            raw_score = (
                W_KEYWORD * keyword_score
                + W_SEMANTIC * semantic_score
                + W_COVERAGE * (coverage * 10)
                + W_CONSISTENCY * consistency_bonus
                + property_bonus
            ) - penalty
            
            # Hard Rule 2: If coverage is between 0.3 and 0.5, apply a 0.5x modifier
            if MIN_COVERAGE_THRESHOLD <= coverage < SOFT_COVERAGE_THRESHOLD:
                raw_score *= 0.5
                
            # Theo yêu cầu fix gọn nhẹ
            safe_raw_score = max(0.0, raw_score)
            confidence_score = safe_raw_score / (safe_raw_score + penalty + 1.0)
            final_percent = confidence_score * 100.0
            
            all_pattern_results.append({
                "pattern": pattern,
                "score": final_percent / 100.0, # Keep score 0-1 range for internal fallback sorting
                "confidence_percent": final_percent,
                "base_score": keyword_score + semantic_score,
                "penalty": penalty,
                "bonus": consistency_bonus,
                "matches": pattern_matches,
                "coverage": coverage,
                "matched_weight": matched_weight,
                "input_total_weight": input_total_weight,
                "heat_score": heat_score,
                "cold_score": cold_score
            })

        if not all_pattern_results:
            logger.info("[INTERNAL-MATCH] No patterns matched even in best-effort mode.")
            return []

        # Rank and filter
        all_pattern_results.sort(key=lambda x: (x["score"], len(x["matches"])), reverse=True)
        
        # Candidate patterns for UI
        candidate_patterns = []
        for res in all_pattern_results[:3]:
            candidate_patterns.append({
                "pattern_id": res["pattern"]["id"],
                "pattern_name": res["pattern"]["name"],
                "score": res["score"],
                "chief_hits": len(res["matches"]),
                "coverage": f"{int(res['coverage']*100)}%"
            })

        # Select top K results
        results = []
        for curr_p in all_pattern_results:
            if len(results) >= top_k:
                break
            # Hard Rule 1 drops bad coverage internally so we can just append top Ks
                
            best_pattern = curr_p["pattern"]
            principles = self.pattern_principles.get(best_pattern["id"], [])
            best_formula = None
            
            if principles:
                best_principle = principles[0]
                formulas = self.principle_formulas.get(best_principle["id"], [])
                if formulas:
                    best_formula = formulas[0]

            if not best_formula:
                continue

            # Full response object
            matched_count = len(curr_p["matches"])
            matched_names = list(set(m["name"] for m in curr_p["matches"]))
            
            # Determine suitability text
            suitability_level = "Thấp"
            if curr_p["confidence_percent"] >= 80:
                suitability_level = "Cao"
            elif curr_p["confidence_percent"] >= 60:
                suitability_level = "Khá"
            elif curr_p["confidence_percent"] >= 40:
                suitability_level = "Trung bình"
                
            reasoning_path = [
                f"Phân tích {valid_input_count} triệu chứng hợp lệ.",
                f"Phát hiện {matched_count}/{valid_input_count} triệu chứng khớp với bệnh cảnh '{best_pattern['name']}'.",
                f"Đạt độ bao phủ trọng số (weighted coverage): {curr_p['matched_weight']:.1f} / {curr_p['input_total_weight']:.1f}.",
            ]
            if curr_p["penalty"] > 0:
                reasoning_path.append(f"Trừ điểm do có triệu chứng ngoại lai hoặc mâu thuẫn: -{curr_p['penalty']}")
            if curr_p["bonus"] > 0:
                reasoning_path.append(f"Cộng điểm ưu tiên do độ đồng nhất cao: +{curr_p['bonus']:.2f}")
            
            if curr_p["heat_score"] > curr_p["cold_score"]:
                reasoning_path.append(f"Chẩn đoán thiên về THỂ NHIỆT (Điểm Nhiệt: {curr_p['heat_score']} > Hàn: {curr_p['cold_score']}).")
            elif curr_p["cold_score"] > curr_p["heat_score"]:
                reasoning_path.append(f"Chẩn đoán thiên về THỂ HÀN (Điểm Hàn: {curr_p['cold_score']} > Nhiệt: {curr_p['heat_score']}).")
            
            reasoning_path.append(f"Xác định phép trị: {best_formula['phep_tri']}")
            reasoning_path.append(f"Đề xuất bài thuốc: {best_formula['name']}")

            # Find missing symptoms (symptoms in pattern but not in input)
            pattern_sid_set = set(best_pattern["symptom_weights"].keys())
            matched_sid_set = set(m["id"] for m in curr_p["matches"])
            missing_sids = pattern_sid_set - matched_sid_set
            missing_names = [self.symptoms[sid]["name"] for sid in missing_sids if sid in self.symptoms]

            # RESTORE WRAPPER FOR LEGACY FRONTEND COMPATIBILITY
            selected_pattern = {
                "id": best_pattern["id"],
                "name": best_pattern["name"],
                "matched_symptoms": [
                    {
                        "symptom_id": str(m["id"]),
                        "symptom_name": str(m["name"]),
                        "weight": best_pattern["symptom_weights"].get(m["id"], 1.0),
                        "contribution": m["score"],
                        "match_method": m["method"]
                    } for m in curr_p["matches"]
                ]
            }

            results.append({
                "name": best_formula["name"],
                "category": "Cổ phương",
                "confidence": round(curr_p["score"], 2),
                "confidence_percent": round(curr_p["confidence_percent"], 1),
                "score": curr_p["score"],
                "coverage": curr_p["coverage"],
                "match_ratio": f"{matched_count}/{valid_input_count}",
                "suitability_level": suitability_level,
                "pattern": best_pattern["name"],
                "principle": best_formula["phep_tri"],
                "indications": best_formula["indications"],
                "usage": "Sắc uống ngày một thang. Chia 2-3 lần uống trong ngày.",
                "ignored_symptoms": ignored_symptoms,
                "explain": {
                    "reasoning": f"Hệ thống xác định bài thuốc phù hợp nhất vì khớp với {matched_count}/{valid_input_count} triệu chứng hợp lệ ({', '.join(matched_names[:3])}...). Độ phù hợp: {suitability_level} ({curr_p['confidence_percent']:.1f}%)." +
                        (f"\nNghiêng về: {'Thể NHIỆT' if curr_p['heat_score'] > curr_p['cold_score'] else 'Thể HÀN' if curr_p['cold_score'] > curr_p['heat_score'] else 'Thể BÌNH HÒA'} (Điểm Nhiệt: {curr_p['heat_score']:.1f}, Điểm Hàn: {curr_p['cold_score']:.1f}).") +
                        f"\nTổng điểm ưu tiên (weight) thu được là {curr_p['matched_weight']:.1f}/{curr_p['input_total_weight']:.1f} điểm." + (
                        f"\n\nCẢNH BÁO: Kết quả có phần thiếu chính xác do chưa đủ triệu chứng quan trọng." if curr_p['coverage'] < SOFT_COVERAGE_THRESHOLD else ""
                    ) + (
                        f"\nLưu ý: Đã tự động bỏ qua các dữ liệu input ảo/không xác định: {', '.join(ignored_symptoms)}." if ignored_symptoms else ""
                    ),
                    "matched": matched_names,
                    "missing": missing_names[:5]
                },
                "normalized_symptoms": normalized_symptoms_for_ui,
                "composition": self.formula_components.get(best_formula["id"], []),
                "candidate_patterns": candidate_patterns,
                "reasoning_path": reasoning_path,
                "priority_layers": [
                    {"layer": "diagnostic", "label": "Biện chứng", "decision": best_pattern["name"], "rationale": f"Khớp {len(curr_p['matches'])} triệu chứng."},
                    {"layer": "therapeutic", "label": "Pháp trị", "decision": best_formula["phep_tri"], "rationale": "Dựa trên thể bệnh đã xác định."}
                ],
                "modifier": {tag: True for tag in detected_user_tags},
                "selected_pattern": selected_pattern # Restored legacy field
            })

        logger.info(f"[INTERNAL-MATCH] Search complete. Returning {len(results)} results.")
        return results

    def suggest_symptoms(self, q: str, limit: int = 10) -> List[dict]:
        """Simple prefix/contains match for UI autocomplete."""
        norm_q = normalize_text(q)
        norm_q_plain = normalize_text(q, remove_accents=True)
        
        if not norm_q: return []
        results = []
        seen = set()
        for sid, data in self.symptoms.items():
            # Match accented or unaccented
            s_norm = data["norm"]
            s_plain = normalize_text(data["name"], remove_accents=True)
            
            if norm_q in s_norm or norm_q_plain in s_plain:
                results.append({"symptom_id": str(sid), "symptom_name": str(data["name"])})
                seen.add(sid)
                if len(results) >= limit: break
        return results
