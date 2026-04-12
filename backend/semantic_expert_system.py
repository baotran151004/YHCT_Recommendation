import re
import unicodedata
from collections import defaultdict
from typing import Any, List, Dict, Optional

from sqlalchemy import text

# System Constants
EXACT_MATCH_POINTS = 2.0
ALIAS_MATCH_POINTS = 1.0
CONFLICT_PENALTY = -2.0
MULTI_MATCH_BONUS = 3.0
MINIMUM_SCORE_THRESHOLD = 3.0

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

def normalize_text(value: str) -> str:
    """Normalize Vietnamese text for consistent matching."""
    if not value:
        return ""
    lowered = value.lower().strip()
    normalized = unicodedata.normalize("NFKD", lowered)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9\s,;/+-]", " ", normalized)
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
            if not manifest: continue
            
            for sid, symptom in self.symptoms.items():
                if symptom["norm"] in manifest:
                    pattern["symptom_weights"][sid] = 1.0
                    count += 1
        print(f"[expert-system] Derived {count} links using keyword matching.")

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
            self.alias_map[normalize_text(name)] = sid
        
        raw_aliases = self._query_rows(db, "SELECT symptom_id, alias FROM symptomalias")
        for row in raw_aliases:
            sid = str(row["symptom_id"])
            alias = str(row["alias"])
            self.alias_map[normalize_text(alias)] = sid

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

    def _infer_tags(self, text: str) -> set:
        tags = set()
        norm_text = normalize_text(text)
        for tag, keywords in PATTERN_TAG_KEYWORDS.items():
            if any(k in norm_text for k in keywords):
                tags.add(tag)
        return tags

    def recommend(self, input_text: str) -> dict:
        """
        Main entry point for recommendation.
        Calculates scores for patterns based on input symptoms and conflicts.
        """
        if not self.ready:
            return {"error": "Expert system is not initialized."}
        
        # 1. Tokenize and Match Symptoms
        input_parts = split_input_parts(input_text)
        matched_symptoms = [] # List of {sid, score}
        detected_user_tags = set()

        for part in input_parts:
            norm_part = normalize_text(part)
            # a. Match exact symptom
            if norm_part in self.alias_map:
                sid = self.alias_map[norm_part]
                score = EXACT_MATCH_POINTS if self.symptoms[sid]["norm"] == norm_part else ALIAS_MATCH_POINTS
                matched_symptoms.append({"id": sid, "score": score, "original": part})
            # b. Partial match (keyword search)
            else:
                for sid, data in self.symptoms.items():
                    if data["norm"] in norm_part or norm_part in data["norm"]:
                        matched_symptoms.append({"id": sid, "score": ALIAS_MATCH_POINTS, "original": part})
                        break
            
            # Detect patient tags (han, nhiet, etc)
            for tag, keywords in CANONICAL_AXIS_RULES.items():
                if any(k in norm_part for k in keywords):
                    detected_user_tags.add(tag)

        if not matched_symptoms:
            return {"error": "Không đủ dữ liệu để gợi ý chính xác"}

        # 2. Score Patterns
        pattern_scores = []
        user_sid_set = {m["id"] for m in matched_symptoms}

        for pid, pattern in self.patterns.items():
            # Base match score
            pattern_matches = [m for m in matched_symptoms if m["id"] in pattern["symptom_weights"]]
            if not pattern_matches:
                continue
            
            base_score = sum(m["score"] for m in pattern_matches)
            
            # Conflict Logic
            penalty = 0.0
            for tag, conflicts in CONFLICT_TAGS.items():
                if tag in detected_user_tags:
                    # User has a tag (e.g. han). Is there a conflict in user's own symptoms?
                    if any(c in detected_user_tags for c in conflicts):
                        penalty += CONFLICT_PENALTY
                    # Or does pattern conflict with user?
                    if any(c in pattern["tags"] for c in conflicts):
                        penalty += CONFLICT_PENALTY
            
            # Bonus: fits many symptoms (> 50% of input or > 3 matches)
            bonus = 0.0
            if len(pattern_matches) / len(input_parts) >= 0.5 or len(pattern_matches) >= 3:
                bonus = MULTI_MATCH_BONUS
            
            total_score = base_score + penalty + bonus
            
            pattern_scores.append({
                "pattern": pattern,
                "score": total_score,
                "match_count": len(pattern_matches)
            })

        if not pattern_scores:
            return {"error": "Không đủ dữ liệu để gợi ý chính xác"}

        # 3. Rank and Select Top Result
        pattern_scores.sort(key=lambda x: (x["score"], x["match_count"]), reverse=True)
        best_p = pattern_scores[0]
        
        if best_p["score"] < MINIMUM_SCORE_THRESHOLD:
            return {"error": "Không đủ dữ liệu để gợi ý chính xác"}

        # 4. Find Formula
        best_pattern = best_p["pattern"]
        principles = self.pattern_principles.get(best_pattern["id"], [])
        best_formula = None
        best_principle = None

        if principles:
            best_principle = principles[0]
            formulas = self.principle_formulas.get(best_principle["id"], [])
            if formulas:
                best_formula = formulas[0]

        if not best_formula:
            return {"error": "Không tìm thấy bài thuốc phù hợp cho thể bệnh này"}

        # 5. Format Explanation
        explanation = f"Triệu chứng: {', '.join(input_parts)}\n"
        explanation += f"→ thuộc thể: {best_pattern['name']}\n"
        explanation += f"→ phép trị: {best_formula['phep_tri']}\n"
        explanation += f"→ bài thuốc: {best_formula['name']}\n\n"
        explanation += f"Lý do: Khớp {best_p['match_count']} triệu chứng cốt yếu. "
        if best_p["score"] > base_score:
            explanation += "Hệ thống xác định độ ưu tiên cao dựa trên sự phù hợp đa triệu chứng."

        return {
            "formula": best_formula["name"],
            "score": best_p["score"],
            "explanation": explanation,
            "pattern_name": best_pattern["name"],
            "principle_name": best_formula['phep_tri']
        }

    def suggest_symptoms(self, q: str, limit: int = 10) -> List[dict]:
        """Simple prefix/contains match for UI autocomplete."""
        norm_q = normalize_text(q)
        if not norm_q: return []
        results = []
        seen = set()
        for sid, data in self.symptoms.items():
            if norm_q in data["norm"]:
                results.append({"symptom_id": sid, "symptom_name": data["name"]})
                seen.add(sid)
                if len(results) >= limit: break
        return results
