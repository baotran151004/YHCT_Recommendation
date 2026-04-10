import math
import re
import unicodedata
from collections import defaultdict
from typing import Any

from sqlalchemy import text

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover
    SentenceTransformer = None
    util = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:  # pragma: no cover
    TfidfVectorizer = None
    cosine_similarity = None


SEMANTIC_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
PRIMARY_SYMPTOM_THRESHOLD = 0.75
SECONDARY_SYMPTOM_THRESHOLD = 0.70
TOP_ALIAS_MATCHES = 5
TOP_PATTERN_CANDIDATES = 5
TOP_PRINCIPLES_PER_PATTERN = 3
CHIEF_SYMPTOM_WEIGHT = 7.0
DERIVED_PATTERN_SYMPTOM_THRESHOLD = 0.34
DERIVED_PATTERN_SYMPTOM_TOP_K = 12
DERIVED_MANIFESTATION_THRESHOLD = 0.78
DERIVED_MANIFESTATION_GAP = 0.06
MIN_PATTERN_COVERAGE = 0.05
MIN_FORMULA_SIMILARITY = 0.05
MIN_SEMANTIC_ALIGNMENT = 0.05
MIN_SCORE_GAP = 0.5

CANONICAL_AXIS_RULES = {
    "bieu": ["so gio", "so lanh", "phat sot", "moi phat", "ngat mui", "dau dau", "ho moi phat", "nong lanh", "nhuc dau", "dau minh", "dau nguoi", "so lanh so nong"],
    "ly": ["khat nuoc", "tao bon", "tieu vang", "dau bung", "day bung", "sot cao", "vat va", "tieu chay", "non oi", "mat nuoc", "phan long", "tieu long"],
    "han": ["so lanh", "lanh", "chan tay lanh", "dom trang", "tieu trong", "thich am", "phan long", "tieu long"],
    "nhiet": ["sot", "sot cao", "khat", "hong do", "dom vang", "mieng kho", "tieu vang", "nong", "phan tao", "tieu do"],
    "hu": ["met moi", "yeu", "hut hoi", "lau ngay", "man tinh", "mo hoi trom", "mat ngu", "da xanh", "gay yeu"],
    "thuc": ["moi bi", "cap tinh", "dot ngot", "dau du doi", "day tuc", "dom nhieu", "bung truong", "tieu chay", "non oi", "nong lanh", "nhuc dau", "phat sot"],
    "dam": ["dom", "nhay", "nang nguc", "buon non", "reo nho", "beo phi", "khac dom"],
    "tao": ["kho hong", "ho khan", "it dom", "mui kho", "da kho", "tao", "mieng kho"],
}

PATTERN_TAG_KEYWORDS = {
    "bieu": ["bieu", "ngoai cam", "giai bieu", "phong han", "phong nhiet", "phong tao"],
    "ly": ["ly", "noi thuong", "phu tang", "truong vi", "ty vi", "can", "tam", "than", "vi quan"],
    "han": ["han", "lanh", "tu han", "hong nhuan", "bach dam"],
    "nhiet": ["nhiet", "nong", "thanh nhiet", "hoa hoa", "dom vang", "hong do"],
    "hu": ["hu", "khi hu", "huyet hu", "am hu", "duong hu", "suy"],
    "thuc": ["thuc", "uat", "tre", "be tac", "truong man", "ta thinh"],
    "dam": ["dam", "dom", "hoa dam", "nhay", "reo nho"],
    "tao": ["tao", "kho", "nhuan tao"],
}

PRINCIPLE_KEYWORDS = {
    "giai_bieu": ["giai bieu", "tan phong", "so phong", "tuyen phe"],
    "thanh_nhiet": ["thanh nhiet", "ta hoa", "tiet hoa", "luong huyet"],
    "on_han": ["tan han", "on trung", "on phe", "hoi duong"],
    "hoa_dam": ["hoa dam", "tru dam"],
    "nhuan_tao": ["nhuan tao", "tu am", "duong am"],
    "bo": ["bo khi", "bo huyet", "bo am", "bo duong", "ich khi", "co sap", "thuoc bo"],
    "chi_ta": ["chi ta", "sap truong", "kien ty", "hoa trung", "giang nghich"],
}

CONFLICT_TAGS = {
    "han": {"nhiet"},
    "nhiet": {"han"},
    "hu": {"thuc"},
    "thuc": {"hu"},
}

CLINICAL_WARNING_RULES = [
    {
        "keywords": ["kho moi", "khat nuoc", "mat nuoc", "tieu it", "chong mat"],
        "warning": "Cần theo dõi nguy cơ hao tổn tân dịch và bổ sung nước, điện giải khi cần.",
    },
    {
        "keywords": ["sot cao", "co giat", "me sang"],
        "warning": "Có dấu hiệu cấp tính, cần theo dõi sát và phối hợp xử trí y học hiện đại nếu cần.",
    },
    {
        "keywords": ["ngat xiu", "da xanh", "kho tho du doi"],
        "warning": "Cần đánh giá cấp cứu ngay nếu có dấu hiệu suy tuần hoàn hoặc suy hô hấp.",
    },
]


def normalize_text(value: str) -> str:
    if not value:
        return ""
    lowered = value.lower().strip()
    normalized = unicodedata.normalize("NFKD", lowered)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9\s,;/+-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def split_input_parts(symptom_text: str) -> list[str]:
    if not symptom_text:
        return []

    raw_parts = [part.strip() for part in re.split(r"[,;\n]+", symptom_text) if part.strip()]
    if len(raw_parts) > 1:
        return raw_parts

    normalized_text = normalize_text(symptom_text)
    joined_parts = [part.strip() for part in re.split(r"\bva\b|\bkem\b|\bkiem\b", normalized_text) if part.strip()]
    if len(joined_parts) > 1:
        return joined_parts

    return raw_parts or [symptom_text.strip()]


def split_manifestation_parts(manifestations: str) -> list[str]:
    if not manifestations:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", manifestations) if part.strip()]


class SemanticExpertSystemEngine:
    def __init__(self, semantic_model_name: str = SEMANTIC_MODEL_NAME):
        self.semantic_model_name = semantic_model_name
        self.model = None
        self.vectorizer = None
        self.encoder_backend = None
        self.ready = False

        self.symptoms: dict[str, dict[str, Any]] = {}
        self.alias_entries: list[dict[str, Any]] = []
        self.patterns: dict[str, dict[str, Any]] = {}
        self.pattern_principles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.principle_formulas: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.formulas: dict[str, dict[str, Any]] = {}
        self.formula_components: dict[str, list[dict[str, Any]]] = defaultdict(list)

        self.alias_embeddings = None
        self.pattern_embeddings = {}
        self.formula_embeddings = {}
        self.pattern_symptom_source = "uninitialized"

    def load(self, session_factory) -> None:
        with session_factory() as db:
            self._load_symptoms(db)
            self._load_patterns(db)
            self._load_principles(db)
            self._load_formulas(db)

        self._load_embeddings()
        has_pattern_links = any(pattern["symptom_weights"] for pattern in self.patterns.values())
        self.ready = bool(self.symptoms and self.patterns and self.formulas and self.alias_entries and has_pattern_links)
        if not self.ready:
            raise RuntimeError("Semantic expert system knowledge base is empty.")

    def suggest_symptoms(self, keyword: str, limit: int = 10) -> list[str]:
        if not keyword or not keyword.strip():
            return []
            
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            return []

        results = []
        seen = set()

        for entry in self.alias_entries:
            if normalized_keyword in entry["semantic_text"]:
                symptom_name = entry["symptom_name"]
                if symptom_name not in seen:
                    seen.add(symptom_name)
                    results.append(symptom_name)
                    if len(results) >= limit:
                        break
        
        return results

    def _query_rows(self, db, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = db.execute(text(sql), params or {})
        rows = [dict(row._mapping) for row in result.fetchall()]
        result.close()
        return rows

    def _load_symptoms(self, db) -> None:
        symptom_rows = self._query_rows(
            db,
            """
            SELECT symptom_id, symptom_name
            FROM Symptom
            """,
        )
        alias_rows = self._query_rows(
            db,
            """
            SELECT symptom_id, alias
            FROM SymptomAlias
            """,
        )

        self.symptoms.clear()
        self.alias_entries.clear()

        for row in symptom_rows:
            symptom_id = str(row.get("symptom_id"))
            symptom_name = (row.get("symptom_name") or "").strip()
            if not symptom_id or not symptom_name:
                continue
            self.symptoms[symptom_id] = {
                "symptom_id": symptom_id,
                "symptom_name": symptom_name,
                "normalized_name": normalize_text(symptom_name),
            }
            self.alias_entries.append(
                {
                    "symptom_id": symptom_id,
                    "symptom_name": symptom_name,
                    "alias": symptom_name,
                    "semantic_text": normalize_text(symptom_name),
                }
            )

        for row in alias_rows:
            symptom_id = str(row.get("symptom_id"))
            alias = (row.get("alias") or "").strip()
            if not symptom_id or not alias or symptom_id not in self.symptoms:
                continue
            self.alias_entries.append(
                {
                    "symptom_id": symptom_id,
                    "symptom_name": self.symptoms[symptom_id]["symptom_name"],
                    "alias": alias,
                    "semantic_text": normalize_text(alias),
                }
            )

    def _load_patterns(self, db) -> None:
        pattern_rows = self._query_rows(
            db,
            """
            SELECT pattern_id, pattern_name_vi, clinical_manifestations
            FROM SyndromePattern
            """,
        )
        pattern_symptom_rows = self._load_pattern_symptom_rows(db)

        self.patterns.clear()
        for row in pattern_rows:
            pattern_id = str(row.get("pattern_id"))
            pattern_name = (row.get("pattern_name_vi") or "").strip()
            if not pattern_id or not pattern_name:
                continue
            manifestations = (row.get("clinical_manifestations") or "").strip()
            search_text = normalize_text(" ".join(filter(None, [pattern_name, manifestations])))
            self.patterns[pattern_id] = {
                "pattern_id": pattern_id,
                "pattern_name": pattern_name,
                "clinical_manifestations": manifestations,
                "semantic_text": search_text,
                "pattern_tags": self._infer_tags(search_text),
                "symptom_weights": {},
                "total_weight": 0.0,
                "chief_symptom_count": 0,
            }

        for row in pattern_symptom_rows:
            pattern_id = str(row.get("pattern_id"))
            symptom_id = str(row.get("symptom_id"))
            if pattern_id not in self.patterns or symptom_id not in self.symptoms:
                continue
            weight = float(row.get("weight") or 1.0)
            self.patterns[pattern_id]["symptom_weights"][symptom_id] = weight
            self.patterns[pattern_id]["total_weight"] += weight
            if weight >= CHIEF_SYMPTOM_WEIGHT:
                self.patterns[pattern_id]["chief_symptom_count"] += 1

    def _load_pattern_symptom_rows(self, db) -> list[dict[str, Any]]:
        table_info = self._find_pattern_symptom_table(db)
        if table_info is None:
            self.pattern_symptom_source = "derived_semantic"
            return []

        schema_name = table_info["schema_name"]
        table_name = table_info["table_name"]
        pattern_column = table_info["pattern_column"]
        symptom_column = table_info["symptom_column"]
        weight_column = table_info["weight_column"]
        qualified_table = f"[{schema_name}].[{table_name}]"
        weight_expression = f"COALESCE([{weight_column}], 1)" if weight_column else "1"

        rows = self._query_rows(
            db,
            f"""
            SELECT
                [{pattern_column}] AS pattern_id,
                [{symptom_column}] AS symptom_id,
                CAST({weight_expression} AS FLOAT) AS weight
            FROM {qualified_table}
            """,
        )
        self.pattern_symptom_source = f"db:{schema_name}.{table_name}"
        return rows

    def _find_pattern_symptom_table(self, db) -> dict[str, str] | None:
        candidate_tables = self._query_rows(
            db,
            """
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
              AND LOWER(TABLE_NAME) LIKE '%pattern%'
              AND LOWER(TABLE_NAME) LIKE '%symptom%'
            ORDER BY
                CASE WHEN TABLE_NAME = 'PatternSymptom' THEN 0 ELSE 1 END,
                TABLE_NAME
            """,
        )

        for table in candidate_tables:
            schema_name = table["TABLE_SCHEMA"]
            table_name = table["TABLE_NAME"]
            column_rows = self._query_rows(
                db,
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :schema_name
                  AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
                """,
                {"schema_name": schema_name, "table_name": table_name},
            )
            columns = [row["COLUMN_NAME"] for row in column_rows]
            normalized = {column.lower(): column for column in columns}

            pattern_column = normalized.get("pattern_id")
            symptom_column = normalized.get("symptom_id")
            weight_column = normalized.get("weight")

            if pattern_column and symptom_column:
                return {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "pattern_column": pattern_column,
                    "symptom_column": symptom_column,
                    "weight_column": weight_column or "",
                }

        return None

    def _infer_tags(self, normalized_text: str) -> set[str]:
        tags = set()
        for tag, keywords in PATTERN_TAG_KEYWORDS.items():
            if any(keyword in normalized_text for keyword in keywords):
                tags.add(tag)
        return tags

    def _infer_principle_tags(self, normalized_text: str) -> set[str]:
        tags = set()
        for tag, keywords in PRINCIPLE_KEYWORDS.items():
            if any(keyword in normalized_text for keyword in keywords):
                tags.add(tag)
        return tags

    def detect_modifier(self, normalized_symptoms: list[dict[str, Any]]) -> dict[str, Any]:
        searchable_text = " ".join(
            filter(
                None,
                [
                    " ".join(normalize_text(item["symptom_name"]) for item in normalized_symptoms),
                    " ".join(normalize_text(item["alias_used"]) for item in normalized_symptoms),
                ],
            )
        )
        modifiers = {
            "han": False,
            "nhiet": False,
            "dam": False,
            "tao": False,
            "hu": False,
            "thuc": False
        }
        evidence_dict = {}

        for axis_key in CANONICAL_AXIS_RULES.keys():
            evidence = sorted({keyword for keyword in CANONICAL_AXIS_RULES[axis_key] if keyword in searchable_text})
            if evidence:
                if axis_key in modifiers:
                    modifiers[axis_key] = True
                evidence_dict[axis_key] = evidence

        return {
            "modifiers": modifiers,
            "evidence": evidence_dict,
            "detected_modifiers": [
                {"key": k, "label": k.capitalize(), "evidence": ev, "score": float(len(ev))}
                for k, ev in evidence_dict.items()
            ],
            "axis_scores": {k: float(len(v)) for k, v in evidence_dict.items()}
        }

    def _score_pattern_modifier_fit(
        self,
        pattern: dict[str, Any],
        axis_scores: dict[str, float],
    ) -> tuple[float, float, list[str]]:
        bonus = 0.0
        penalty = 0.0
        reasons: list[str] = []
        tags = pattern.get("pattern_tags", set())

        for axis_key, score in axis_scores.items():
            if score <= 0:
                continue
            if axis_key in tags:
                axis_bonus = min(score * 2.2, 6.0)
                bonus += axis_bonus
                reasons.append(f"pattern phu hop truc {axis_key} (+{axis_bonus:.1f})")
            for conflict_key in CONFLICT_TAGS.get(axis_key, set()):
                if conflict_key in tags:
                    axis_penalty = min(score * 3.0, 8.0)
                    penalty += axis_penalty
                    reasons.append(f"pattern xung dot truc {axis_key}/{conflict_key} (-{axis_penalty:.1f})")

        return bonus, penalty, reasons

    def _score_formula_priority(
        self,
        formula: dict[str, Any],
        principle: dict[str, Any],
        modifier_context: dict[str, Any],
        pattern_candidate: dict[str, Any],
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        axis_scores = modifier_context["axis_scores"]
        principle_tags = set(principle.get("tags", set()))
        formula_tags = set(formula.get("tags", set()))
        merged_tags = principle_tags | formula_tags

        if axis_scores.get("bieu", 0.0) >= 1 and "giai_bieu" in merged_tags:
            score += 7.0
            reasons.append("co bieu chung, uu tien giai bieu")
        if axis_scores.get("nhiet", 0.0) >= 1 and "thanh_nhiet" in merged_tags:
            score += 4.0
            reasons.append("co nhiet tuong, uu tien thanh nhiet")
        if axis_scores.get("han", 0.0) >= 1 and "on_han" in merged_tags:
            score += 4.0
            reasons.append("co han tuong, uu tien on han")
        if axis_scores.get("dam", 0.0) >= 1 and "hoa_dam" in merged_tags:
            score += 3.5
            reasons.append("co dam, uu tien hoa dam")
        if axis_scores.get("tao", 0.0) >= 1 and "nhuan_tao" in merged_tags:
            score += 3.5
            reasons.append("co tao, uu tien nhuan tao")
        if axis_scores.get("ly", 0.0) >= 1 and "chi_ta" in merged_tags:
            score += 3.0
            reasons.append("co ly chung tieu hoa, uu tien hoa trung/chi ta")

        # Clinical Logic: Ngoai cam so khoi bat nghi bo (Don't use tonics in early external infections)
        formula_cat = formula.get("category", "").lower()
        if axis_scores.get("bieu", 0.0) >= 1:
            if "bo" in merged_tags or "bo" in formula_cat or "ich" in formula_cat:
                score -= 12.0
                reasons.append("co bieu chung, nghiem cam dung thuoc bo (dong cua nhot giac)")
            if "on trung" in formula_cat or "on ly" in formula_cat:
                score -= 10.0
                reasons.append("co bieu chung, chua dung thuoc on trung ly (nguy co nhiet hoa)")
            if "giải biểu" in formula_cat or "tuyên phế" in formula_cat or "thanh nhiệt" in formula_cat:
                score += 8.0
                reasons.append("uu tien bai thuoc giai bieu/thanh nhiet theo dung phep tri")

        if axis_scores.get("thuc", 0.0) >= 1 and ("bo" in merged_tags or "bo" in formula_cat):
            score -= 9.0
            reasons.append("dang nghien ve thuc chung, ha uu tien bai bo")
        if axis_scores.get("ly", 0.0) >= 1 and axis_scores.get("hu", 0.0) == 0 and ("bo" in merged_tags or "bo" in formula_cat):
            score -= 8.0
            reasons.append("ly chung cap tinh, chua uu tien huu bo")
        if pattern_candidate["pattern_coverage"] < 0.15 and ("bo" in merged_tags or "bo" in formula_cat):
            score -= 7.0
            reasons.append("pattern do phu thap, khong uu tien bai bo")
        if pattern_candidate["chief_hits"] == 0 and ("bo" in merged_tags or "bo" in formula_cat):
            score -= 4.0
            reasons.append("thieu trong chung, giam uu tien bai bo")

        return score, reasons

    def _collect_clinical_warnings(self, normalized_symptoms: list[dict[str, Any]]) -> list[str]:
        searchable_text = " ".join(
            filter(
                None,
                [
                    " ".join(normalize_text(item["symptom_name"]) for item in normalized_symptoms),
                    " ".join(normalize_text(item["alias_used"]) for item in normalized_symptoms),
                ],
            )
        )
        warnings = []
        for rule in CLINICAL_WARNING_RULES:
            if any(keyword in searchable_text for keyword in rule["keywords"]):
                warnings.append(rule["warning"])
        return warnings

    def _load_principles(self, db) -> None:
        rows = self._query_rows(
            db,
            """
            SELECT
                pp.pattern_id,
                pp.principle_id,
                COALESCE(pp.priority_level, 0) AS priority_level,
                tp.principle_name_vi
            FROM PatternPrinciple pp
            JOIN TherapeuticPrinciple tp ON tp.principle_id = pp.principle_id
            """,
        )

        self.pattern_principles.clear()
        for row in rows:
            pattern_id = str(row.get("pattern_id"))
            principle_id = str(row.get("principle_id"))
            principle_name = (row.get("principle_name_vi") or "").strip()
            if not pattern_id or not principle_id or not principle_name:
                continue
            principle_text = normalize_text(principle_name)
            self.pattern_principles[pattern_id].append(
                {
                    "principle_id": principle_id,
                    "principle_name": principle_name,
                    "priority_level": int(row.get("priority_level") or 0),
                    "tags": self._infer_principle_tags(principle_text),
                }
            )

        for pattern_id, principles in self.pattern_principles.items():
            principles.sort(key=lambda item: item["priority_level"], reverse=True)

    def _load_formulas(self, db) -> None:
        formula_rows = self._query_rows(
            db,
            """
            SELECT
                f.formula_id,
                f.formula_name_vi,
                f.formula_category,
                f.indications,
                f.usage_tcm
            FROM Formula f
            """,
        )
        formula_principle_rows = self._query_rows(
            db,
            """
            SELECT formula_id, principle_id
            FROM FormulaPrinciple
            """,
        )
        component_rows = self._query_rows(
            db,
            """
            SELECT
                fc.formula_id,
                fc.herb_id,
                fc.dosage_value,
                fc.dosage_unit,
                fc.dosage_note,
                hm.herb_name_vi,
                hm.image_url
            FROM FormulaComponent fc
            LEFT JOIN HerbMaterial hm ON hm.herb_id = fc.herb_id
            """,
        )

        self.formulas.clear()
        self.principle_formulas.clear()
        self.formula_components.clear()

        for row in component_rows:
            formula_id = str(row.get("formula_id"))
            if not formula_id:
                continue
            self.formula_components[formula_id].append(
                {
                    "name": row.get("herb_name_vi") or row.get("herb_id") or "N/A",
                    "dosage": row.get("dosage_value"),
                    "unit": row.get("dosage_unit") or "",
                    "note": row.get("dosage_note"),
                    "image": row.get("image_url"),
                }
            )

        for row in formula_rows:
            formula_id = str(row.get("formula_id"))
            formula_name = (row.get("formula_name_vi") or "").strip()
            if not formula_id or not formula_name:
                continue
            category = row.get("formula_category") or "N/A"
            indications = row.get("indications") or ""
            usage = row.get("usage_tcm") or "Dang cap nhat..."
            search_text = normalize_text(" ".join(filter(None, [formula_name, category, indications, usage])))
            self.formulas[formula_id] = {
                "formula_id": formula_id,
                "name": formula_name,
                "category": category,
                "indications": indications,
                "usage": usage,
                "composition": self.formula_components.get(formula_id, []),
                "semantic_text": search_text,
                "tags": self._infer_principle_tags(search_text),
            }

        for row in formula_principle_rows:
            formula_id = str(row.get("formula_id"))
            principle_id = str(row.get("principle_id"))
            if formula_id in self.formulas and principle_id:
                self.principle_formulas[principle_id].append(self.formulas[formula_id])

    def _load_embeddings(self) -> None:
        alias_texts = [entry["semantic_text"] for entry in self.alias_entries]
        pattern_ids = list(self.patterns.keys())
        pattern_texts = [self.patterns[pattern_id]["semantic_text"] for pattern_id in pattern_ids]
        formula_ids = list(self.formulas.keys())
        formula_texts = [self.formulas[formula_id]["semantic_text"] for formula_id in formula_ids]
        if SentenceTransformer is not None and util is not None:
            try:
                self.model = SentenceTransformer(self.semantic_model_name, local_files_only=True)
                self.encoder_backend = "sentence_transformer"
                self.alias_embeddings = self.model.encode(alias_texts, convert_to_tensor=True)
                if pattern_texts:
                    pattern_vectors = self.model.encode(pattern_texts, convert_to_tensor=True)
                    self.pattern_embeddings = {pattern_id: pattern_vectors[index] for index, pattern_id in enumerate(pattern_ids)}
                if formula_texts:
                    formula_vectors = self.model.encode(formula_texts, convert_to_tensor=True)
                    self.formula_embeddings = {formula_id: formula_vectors[index] for index, formula_id in enumerate(formula_ids)}
                self._derive_pattern_symptom_links_if_needed()
                return
            except Exception as exc:
                print(f"[semantic-engine] sentence-transformer unavailable, fallback to tfidf: {exc}")
                self.model = None

        if TfidfVectorizer is None or cosine_similarity is None:
            raise RuntimeError("No semantic encoder is available. Install sentence-transformers or scikit-learn.")

        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        self.vectorizer.fit(alias_texts + pattern_texts + formula_texts)
        self.encoder_backend = "tfidf_char_ngram"
        self.alias_embeddings = self.vectorizer.transform(alias_texts)
        if pattern_texts:
            pattern_vectors = self.vectorizer.transform(pattern_texts)
            self.pattern_embeddings = {pattern_id: pattern_vectors[index] for index, pattern_id in enumerate(pattern_ids)}
        if formula_texts:
            formula_vectors = self.vectorizer.transform(formula_texts)
            self.formula_embeddings = {formula_id: formula_vectors[index] for index, formula_id in enumerate(formula_ids)}

        self._derive_pattern_symptom_links_if_needed()

    def _encode_text(self, value: str):
        if self.encoder_backend == "sentence_transformer":
            return self.model.encode([value], convert_to_tensor=True)[0]
        return self.vectorizer.transform([value])

    def _similarity_scores(self, query_embedding, target_embeddings):
        if self.encoder_backend == "sentence_transformer":
            return util.cos_sim(query_embedding, target_embeddings)[0]
        return cosine_similarity(query_embedding, target_embeddings)[0]

    def _pair_similarity(self, left_embedding, right_embedding) -> float:
        if self.encoder_backend == "sentence_transformer":
            return float(util.cos_sim(left_embedding, right_embedding).item())
        return float(cosine_similarity(left_embedding, right_embedding)[0][0])

    def _derive_pattern_symptom_links_if_needed(self) -> None:
        needs_derivation = any(not pattern["symptom_weights"] for pattern in self.patterns.values())
        if not needs_derivation or self.alias_embeddings is None:
            return

        for pattern in self.patterns.values():
            if pattern["symptom_weights"]:
                continue

            symptom_scores: dict[str, float] = {}
            manifestation_parts = split_manifestation_parts(pattern["clinical_manifestations"])
            for manifestation in manifestation_parts:
                normalized_manifestation = normalize_text(manifestation)
                if not normalized_manifestation:
                    continue
                matched = self._select_manifestation_match(normalized_manifestation)
                if matched is None:
                    continue
                symptom_id, score = matched
                symptom_scores[symptom_id] = max(symptom_scores.get(symptom_id, 0.0), score)

            if not symptom_scores:
                continue

            for symptom_id, score in symptom_scores.items():
                synthetic_weight = round(5.5 + score * 4.5, 2)
                pattern["symptom_weights"][symptom_id] = synthetic_weight

            pattern["total_weight"] = sum(pattern["symptom_weights"].values())
            pattern["chief_symptom_count"] = sum(
                1 for weight in pattern["symptom_weights"].values() if weight >= CHIEF_SYMPTOM_WEIGHT
            )

    def _rank_alias_candidates(self, query_embedding, top_k: int) -> list[tuple[float, int]]:
        similarities = self._similarity_scores(query_embedding, self.alias_embeddings)
        if self.encoder_backend == "sentence_transformer":
            top_scores, top_indices = similarities.topk(min(top_k, len(self.alias_entries)))
            return [
                (float(score_tensor.item()), int(index_tensor.item()))
                for score_tensor, index_tensor in zip(top_scores, top_indices)
            ]

        indexed_scores = [(float(score), index) for index, score in enumerate(similarities)]
        return sorted(indexed_scores, key=lambda item: item[0], reverse=True)[:top_k]

    def _select_manifestation_match(self, normalized_manifestation: str) -> tuple[str, float] | None:
        exact_entry = next(
            (entry for entry in self.alias_entries if entry["semantic_text"] == normalized_manifestation),
            None,
        )
        if exact_entry is not None:
            return exact_entry["symptom_id"], 1.0

        manifestation_embedding = self._encode_text(normalized_manifestation)
        ranked_items = self._rank_alias_candidates(manifestation_embedding, top_k=2)
        if not ranked_items:
            return None

        best_score, best_index = ranked_items[0]
        if best_score < DERIVED_MANIFESTATION_THRESHOLD:
            return None

        if len(ranked_items) > 1:
            second_score = ranked_items[1][0]
            if best_score - second_score < DERIVED_MANIFESTATION_GAP:
                return None

        best_entry = self.alias_entries[best_index]
        return best_entry["symptom_id"], float(best_score)

    def _semantic_candidates_from_embedding(self, phrase_embedding) -> list[dict[str, Any]]:
        similarities = self._similarity_scores(phrase_embedding, self.alias_embeddings)
        top_k = min(TOP_ALIAS_MATCHES, len(self.alias_entries))
        if top_k == 0:
            return []

        aggregated: dict[str, dict[str, Any]] = {}
        if self.encoder_backend == "sentence_transformer":
            top_scores, top_indices = similarities.topk(top_k)
            ranked_items = [
                (float(score_tensor.item()), int(index_tensor.item()))
                for score_tensor, index_tensor in zip(top_scores, top_indices)
            ]
        else:
            indexed_scores = [(float(score), index) for index, score in enumerate(similarities)]
            ranked_items = sorted(indexed_scores, key=lambda item: item[0], reverse=True)[:top_k]

        for rank, (score, index) in enumerate(ranked_items, start=1):
            entry = self.alias_entries[index]
            symptom_id = entry["symptom_id"]
            if symptom_id not in aggregated or score > aggregated[symptom_id]["semantic_score"]:
                aggregated[symptom_id] = {
                    "symptom_id": symptom_id,
                    "symptom_name": entry["symptom_name"],
                    "alias_used": entry["alias"],
                    "semantic_score": round(score, 4),
                    "rank": rank,
                }

        candidates = sorted(aggregated.values(), key=lambda item: item["semantic_score"], reverse=True)
        if not candidates:
            return []

        strong = [item for item in candidates if item["semantic_score"] >= PRIMARY_SYMPTOM_THRESHOLD]
        if strong:
            return strong

        if candidates[0]["semantic_score"] >= SECONDARY_SYMPTOM_THRESHOLD:
            return [candidates[0]]
        return []

    def normalize_input(self, symptom_text: str) -> dict[str, Any]:
        input_parts = split_input_parts(symptom_text)
        part_records = []
        for raw_part in input_parts:
            normalized_part = normalize_text(raw_part)
            if normalized_part:
                part_records.append((raw_part, normalized_part))

        if not part_records:
            return {"input_parts": [], "normalized_symptoms": [], "unmatched_parts": []}

        normalized_parts = [record[1] for record in part_records]
        if self.encoder_backend == "sentence_transformer":
            part_embeddings = self.model.encode(normalized_parts, convert_to_tensor=True)
        else:
            part_embeddings = self.vectorizer.transform(normalized_parts)
        aggregated_symptoms: dict[str, dict[str, Any]] = {}
        unmatched_parts: list[str] = []

        for index, (raw_part, normalized_part) in enumerate(part_records):
            candidates = self._semantic_candidates_from_embedding(part_embeddings[index])
            if not candidates:
                unmatched_parts.append(raw_part)
                continue

            best_candidate = candidates[0]
            symptom_id = best_candidate["symptom_id"]
            current = aggregated_symptoms.get(symptom_id)
            payload = {
                "symptom_id": symptom_id,
                "symptom_name": best_candidate["symptom_name"],
                "alias_used": best_candidate["alias_used"],
                "semantic_score": best_candidate["semantic_score"],
                "match_method": "semantic",
                "raw_inputs": [raw_part],
            }

            if current is None or payload["semantic_score"] > current["semantic_score"]:
                aggregated_symptoms[symptom_id] = payload
            else:
                current["raw_inputs"].append(raw_part)

        return {
            "input_parts": input_parts,
            "normalized_symptoms": list(aggregated_symptoms.values()),
            "unmatched_parts": unmatched_parts,
        }

    def score_patterns(
        self,
        normalized_symptoms: list[dict[str, Any]],
        modifier_data: dict[str, Any],
        query_embedding,
        input_part_count: int,
    ) -> list[dict[str, Any]]:
        scored_patterns = []
        modifiers = modifier_data.get("modifiers", {})
        
        for pattern in self.patterns.values():
            matched_symptoms = []
            weighted_match_score = 0.0
            chief_hits = 0
            
            for symptom in normalized_symptoms:
                weight = pattern["symptom_weights"].get(symptom["symptom_id"])
                if weight is None:
                    continue
                contribution = weight * symptom["semantic_score"]
                weighted_match_score += contribution
                if weight >= CHIEF_SYMPTOM_WEIGHT:
                    chief_hits += 1
                matched_symptoms.append({
                    "symptom_id": symptom["symptom_id"],
                    "symptom_name": symptom["symptom_name"],
                    "weight": round(weight, 2),
                    "semantic_score": symptom["semantic_score"],
                    "contribution": round(contribution, 2)
                })
                
            if not matched_symptoms:
                continue
                
            coverage = len(matched_symptoms) / max(len(pattern["symptom_weights"]), 1)
            pattern_tags = set(pattern.get("pattern_tags", []))
            modifier_score = 0.0
            modifier_reasons = []
            
            if modifiers.get("nhiet") and "nhiet" in pattern_tags:
                modifier_score += 2.0
                modifier_reasons.append("Cộng điểm: phù hợp dấu hiệu nhiệt")
            
            if modifiers.get("han") and "han" in pattern_tags:
                modifier_score += 2.0
                modifier_reasons.append("Cộng điểm: phù hợp dấu hiệu hàn")
                    
            for mod in ["dam", "tao", "hu", "thuc"]:
                if modifiers.get(mod) and mod in pattern_tags:
                    modifier_score += 1.5
                    modifier_reasons.append(f"Cộng điểm: phù hợp dấu hiệu {mod}")

            pattern_semantic_score = 0.0
            if pattern["pattern_id"] in self.pattern_embeddings:
                pattern_semantic_score = max(
                    self._pair_similarity(query_embedding, self.pattern_embeddings[pattern["pattern_id"]]),
                    0.0,
                )

            final_score = weighted_match_score + modifier_score + pattern_semantic_score * 1.5
            
            scored_patterns.append({
                "pattern_id": pattern["pattern_id"],
                "pattern_name": pattern["pattern_name"],
                "pattern": pattern,
                "pattern_tags": sorted(pattern_tags),
                "matched_symptoms": matched_symptoms,
                "weighted_match_score": round(weighted_match_score, 3),
                "pattern_coverage": round(coverage, 3),
                "coverage": round(coverage, 3),
                "chief_hits": chief_hits,
                "semantic_alignment": round(pattern_semantic_score, 3),
                "modifier_bonus": round(modifier_score, 3),
                "modifier_penalty": 0.0,
                "modifier_reasons": modifier_reasons,
                "final_score": round(final_score, 3)
            })
            
        scored_patterns.sort(key=lambda x: (x["final_score"], x["coverage"]), reverse=True)
        return scored_patterns

    def apply_conflict_rules(
        self,
        scored_patterns: list[dict[str, Any]],
        modifier_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        modifiers = modifier_data.get("modifiers", {})
        evidence = modifier_data.get("evidence", {})
        
        filtered_patterns = []
        for p in scored_patterns:
            pattern_tags = p["pattern_tags"]
            reasons = list(p.get("modifier_reasons", []))
            conflict_penalty = 0.0
            is_valid = True
            
            has_dry_thirst = any(k in evidence.get("nhiet", []) for k in ["khat"]) or any(k in evidence.get("tao", []) for k in ["kho", "khat", "kho mong"])
            if has_dry_thirst and "han" in pattern_tags:
                is_valid = False
                reasons.append("Loại trừ: có khô/khát nhưng pattern là hàn")
                
            if modifiers.get("nhiet") and "han" in pattern_tags:
                is_valid = False
                reasons.append("Loại trừ: mâu thuẫn nhiệt - hàn")
            
            if modifiers.get("han") and "nhiet" in pattern_tags:
                is_valid = False
                reasons.append("Loại trừ: mâu thuẫn hàn - nhiệt")

            if modifiers.get("hu") and "thuc" in pattern_tags:
                conflict_penalty += 3.0
                reasons.append("Penalty (-3.0): mâu thuẫn hư - thực")
                
            if modifiers.get("thuc") and "hu" in pattern_tags:
                conflict_penalty += 3.0
                reasons.append("Penalty (-3.0): mâu thuẫn thực - hư")

            if not is_valid:
                continue
                
            if modifiers.get("dam") and "dam" in pattern_tags:
                p["modifier_bonus"] += 4.0 # Boost further
                p["final_score"] += 4.0
                reasons.append("Ưu tiên (+4.0): có đờm => ưu tiên pattern đàm")
            
            p["modifier_penalty"] = conflict_penalty
            p["final_score"] -= conflict_penalty
            p["modifier_reasons"] = reasons
            filtered_patterns.append(p)
            
        filtered_patterns.sort(key=lambda x: (x["final_score"], x["coverage"]), reverse=True)
        return filtered_patterns

    def select_formula_candidates(
        self,
        scored_patterns: list[dict[str, Any]],
        modifier_context: dict[str, Any],
        query_embedding,
    ) -> list[dict[str, Any]]:
        candidates = []

        for pattern in scored_patterns[:TOP_PATTERN_CANDIDATES]:
            for principle in self.pattern_principles.get(pattern["pattern_id"], [])[:TOP_PRINCIPLES_PER_PATTERN]:
                principle_bonus = principle["priority_level"] * 2.0
                for formula in self.principle_formulas.get(principle["principle_id"], []):
                    formula_vector = self.formula_embeddings.get(formula["formula_id"])
                    formula_similarity = 0.0
                    if formula_vector is not None:
                        formula_similarity = max(self._pair_similarity(query_embedding, formula_vector), 0.0)

                    formula_adjustment, formula_reasons = self._score_formula_priority(
                        formula,
                        principle,
                        modifier_context,
                        pattern,
                    )
                    score = pattern["final_score"] + principle_bonus + formula_adjustment + formula_similarity * 1.5
                    candidates.append(
                        {
                            "formula": formula,
                            "pattern": pattern,
                            "principle": principle,
                            "formula_similarity": round(formula_similarity, 3),
                            "formula_reasons": formula_reasons,
                            "score": round(score, 3),
                        }
                    )

        deduped: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            formula_id = candidate["formula"]["formula_id"]
            if formula_id not in deduped or candidate["score"] > deduped[formula_id]["score"]:
                deduped[formula_id] = candidate

        ranked = list(deduped.values())
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _calculate_confidence(
        self,
        selected_candidate: dict[str, Any],
        normalization_result: dict[str, Any],
        all_candidates: list[dict[str, Any]],
    ) -> float:
        # Confidence score upgraded logic
        matched_count = len(selected_candidate["pattern"]["matched_symptoms"])
        mapped_count = max(len(normalization_result["normalized_symptoms"]), 1)
        
        # Max possible score logic
        max_possible_weight = selected_candidate["pattern"]["pattern"].get("total_weight", 10.0)
        modifier_bonus = selected_candidate["pattern"].get("modifier_bonus", 0.0)
        max_possible_score = max_possible_weight + modifier_bonus + 1.5 
        
        # If perfect match on weight + bonus + semantic alignment max (1.5)
        score = selected_candidate["score"]
        
        confidence = score / max(max_possible_score, 1.0)
        
        # Bonus factor for high coverage
        coverage = matched_count / mapped_count
        if coverage > 0.8:
            confidence += 0.1
            
        confidence = min(max(confidence, 0.1), 1.0)
        return round(confidence, 2)

    def _evaluate_recommendation_reliability(
        self,
        selected_candidate: dict[str, Any],
        normalization_result: dict[str, Any],
        modifier_context: dict[str, Any],
        all_candidates: list[dict[str, Any]],
    ) -> tuple[bool, list[str]]:
        pattern = selected_candidate["pattern"]
        mapped_count = len(normalization_result["normalized_symptoms"])
        matched_count = len(pattern["matched_symptoms"])
        input_coverage = matched_count / max(mapped_count, 1)
        chief_hits = pattern["chief_hits"]
        formula_similarity = selected_candidate["formula_similarity"]
        semantic_alignment = pattern["semantic_alignment"]
        pattern_coverage = pattern["pattern_coverage"]
        axis_scores = modifier_context["axis_scores"]
        formula_tags = set(selected_candidate["formula"].get("tags", set()))
        principle_tags = set(selected_candidate["principle"].get("tags", set()))
        merged_tags = formula_tags | principle_tags
        reasons: list[str] = []

        # Dynamic reliability thresholds based on input complexity
        if mapped_count <= 2:
            minimum_matches = 1
            minimum_input_coverage = 0.30 
        elif mapped_count <= 4:
            minimum_matches = 1 
            minimum_input_coverage = 0.15 
        else:
            minimum_matches = 1
            minimum_input_coverage = 0.20

        if matched_count < minimum_matches:
            reasons.append(f"matched_count={matched_count} < minimum_matches={minimum_matches}")
        if input_coverage < minimum_input_coverage:
            reasons.append(
                f"input_coverage={round(input_coverage, 3)} < minimum_input_coverage={minimum_input_coverage}"
            )
        if pattern_coverage < (MIN_PATTERN_COVERAGE * 0.8): # Relax pattern coverage slightly
            reasons.append(f"pattern_coverage={pattern_coverage} < minimum={MIN_PATTERN_COVERAGE * 0.8}")

        has_semantic_support = (
            chief_hits > 0
            or formula_similarity >= MIN_FORMULA_SIMILARITY
            or semantic_alignment >= MIN_SEMANTIC_ALIGNMENT
            or input_coverage >= 0.5
        )
        if not has_semantic_support:
            reasons.append(
                "candidate lacks chief-hit or sufficient semantic support "
                f"(chief_hits={chief_hits}, formula_similarity={formula_similarity}, semantic_alignment={semantic_alignment})"
            )

        if len(all_candidates) > 1:
            score_gap = selected_candidate["score"] - all_candidates[1]["score"]
            if score_gap < MIN_SCORE_GAP and matched_count <= 1 and chief_hits == 0 and formula_similarity < 0.14:
                reasons.append(f"score_gap={round(score_gap, 3)} too small for a weakly-supported top candidate")

        if axis_scores.get("ly", 0.0) >= 1 and axis_scores.get("hu", 0.0) == 0 and "bo" in merged_tags:
            reasons.append("ly chung ro nhung formula dang nghien ve bo")
        if axis_scores.get("thuc", 0.0) >= 1 and "bo" in merged_tags:
            reasons.append("thuc chung ro nhung formula dang nghien ve bo")

        return len(reasons) == 0, reasons

    def generate_explain(self, pattern_info: dict[str, Any], modifier_data: dict[str, Any], principle_info: dict[str, Any]) -> dict[str, Any]:
        pattern_data = self.patterns.get(pattern_info["pattern_id"], {})
        matched_symptoms = [s["symptom_name"] for s in pattern_info["matched_symptoms"]]
        matched_ids = {s["symptom_id"] for s in pattern_info["matched_symptoms"]}
        
        missing_symptoms = []
        for symptom_id in pattern_data.get("symptom_weights", {}).keys():
            if symptom_id not in matched_ids:
                if symptom_id in self.symptoms:
                    missing_symptoms.append(self.symptoms[symptom_id]["symptom_name"])
                    
        modifier_detected = {k: v for k, v in modifier_data.get("modifiers", {}).items() if v}
        
        reason_parts = []
        if matched_symptoms:
            reason_parts.append(f"Triệu chứng {', '.join(matched_symptoms[:3])} → {pattern_info['pattern_name']}")
        
        detected_keys = list(modifier_detected.keys())
        if detected_keys:
            reason_parts.append(f"kèm dấu hiệu {', '.join(detected_keys)} → củng cố bệnh lý")
            
        reason_parts.append(f"→ Chọn phép {principle_info['principle_name']}")

        reasoning_text = ", ".join(reason_parts)
            
        return {
            "matched": matched_symptoms,
            "missing": missing_symptoms,
            "modifier": modifier_detected,
            "reasoning": reasoning_text
        }

    def recommend(self, symptom_text: str, top_k: int = 1) -> list[dict[str, Any]]:
        if not self.ready:
            raise RuntimeError("SemanticExpertSystemEngine has not been loaded.")

        normalization_result = self.normalize_input(symptom_text)
        if not normalization_result["input_parts"] or not normalization_result["normalized_symptoms"]:
            return []

        modifier_context = self.detect_modifier(normalization_result["normalized_symptoms"])
        normalized_query = normalize_text(symptom_text)
        query_embedding = self._encode_text(normalized_query)

        scored_patterns = self.score_patterns(
            normalization_result["normalized_symptoms"],
            modifier_context,
            query_embedding,
            len(normalization_result["input_parts"]),
        )
        if not scored_patterns:
            return []

        prioritized_patterns = self.apply_conflict_rules(scored_patterns, modifier_context)
        formula_candidates = self.select_formula_candidates(prioritized_patterns, modifier_context, query_embedding)
        
        if not formula_candidates:
            return []

        selected_candidate = None
        for candidate in formula_candidates:
            is_reliable, rejection_reasons = self._evaluate_recommendation_reliability(
                candidate,
                normalization_result,
                modifier_context,
                formula_candidates,
            )
            if is_reliable:
                selected_candidate = candidate
                break

        if selected_candidate is None:
            # Fallback to the top candidate if all were rejected (relax constraints)
            if len(formula_candidates) > 0:
                selected_candidate = formula_candidates[0]
            else:
                return []

        formula = selected_candidate["formula"]
        pattern = selected_candidate["pattern"]
        principle = selected_candidate["principle"]
        explain_data = self.generate_explain(pattern, modifier_context, principle)

        # Trả về output JSON đúng chuẩn theo format yêu cầu
        result = {
            "formula": formula["name"],
            "pattern": pattern["pattern_name"],
            "principle": principle["principle_name"],
            "score": round(selected_candidate["score"], 2),
            "coverage": pattern["coverage"],
            "confidence": self._calculate_confidence(selected_candidate, normalization_result, formula_candidates),
            "modifiers": modifier_context.get("modifiers", {}),
            "explain": explain_data,
            # Bổ sung các fields phụ bên dưới để tương thích ngược tạm thời với UI cũ
            "name": formula["name"],
            "category": formula.get("category", ""),
            "indications": formula.get("indications", ""),
            "composition": formula.get("composition", []),
            "usage": formula.get("usage", ""),
            "matched_symptoms": explain_data["matched"],
            "selected_pattern": {
                "pattern_id": pattern["pattern_id"],
                "pattern_name": pattern["pattern_name"],
                "score": pattern["final_score"],
                "coverage": pattern["coverage"]
            },
            "therapeutic_principle": {
                "principle_id": principle["principle_id"],
                "principle_name": principle["principle_name"],
            },
            "clinical_warnings": self._collect_clinical_warnings(normalization_result["normalized_symptoms"])
        }

        return [result][: max(1, top_k)]
