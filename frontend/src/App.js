import React, { useState } from "react";
import "./App.css";
import {
  FaSearch,
  FaLeaf,
  FaFlask,
  FaInfoCircle,
  FaExclamationTriangle,
  FaChevronDown,
  FaChevronUp,
} from "react-icons/fa";

function formatAxis(value) {
  if (!value) return "N/A";
  return value.replaceAll("_", " ");
}

function formatMatchMethod(value) {
  if (!value) return "N/A";
  if (value === "exact") return "Exact";
  if (value === "contains") return "Contains";
  if (value === "semantic") return "Semantic";
  return value;
}

const MODIFIER_LABELS = {
  han: "Hàn",
  nhiet: "Nhiệt",
  hu: "Hư",
  thuc: "Thực",
  dam: "Đàm",
  tao: "Táo",
  bieu: "Biểu",
  ly: "Lý"
};

function formatModifier(key) {
  return MODIFIER_LABELS[key.toLowerCase()] || key.toUpperCase();
}

function App() {
  const [symptom, setSymptom] = useState("");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  const handleSearch = async () => {
    if (!symptom.trim()) return;

    setLoading(true);
    setExpandedId(null);
    setData([]);

    try {
      const res = await fetch(`/expert-system/recommend?symptom=${encodeURIComponent(symptom)}&top_k=1`);
      const result = await res.json();
      setData(Array.isArray(result) ? result : []);
    } catch (err) {
      console.error("Fetch error:", err);
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (index) => {
    setExpandedId((current) => (current === index ? null : index));
  };

  return (
    <div className="container">
      <header className="header">
        <h1>Hệ Thống Gợi Ý Bài Thuốc YHCT Việt Nam</h1>
        <p>Gợi ý bài thuốc thông minh ứng dụng Biện chứng luận trị & Semantic AI.</p>
      </header>

      <div className="search-wrapper">
        <FaSearch className="search-icon" />
        <input
          value={symptom}
          onChange={(e) => setSymptom(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="VD: gai gai rét, hắt xì, đau đau mỏi người, ho viêm họng..."
        />
        <button onClick={handleSearch} disabled={loading || !symptom.trim()}>
          Gợi ý
        </button>
      </div>

      {loading && (
        <div className="loader-container">
          <div className="spinner"></div>
          <p>Hệ thống đang phân tích triệu chứng qua Semantic AI...</p>
        </div>
      )}

      {!loading && symptom && data.length === 0 && (
        <div className="empty">
          <p>Chưa tìm thấy bài thuốc nào thật sự phù hợp. Vui lòng mô tả chi tiết và tự nhiên hơn các triệu chứng hiện tại.</p>
        </div>
      )}

      <div className="results-list">
        {data.map((item, index) => {
          const isExpanded = expandedId === index;
          const pattern = item.selected_pattern || {};
          const principle = item.therapeutic_principle || {};
          const axes = item.diagnostic_axes || {};
          const normalizedSymptoms = item.normalized_symptoms || [];
          const modifiers = item.detected_modifiers || [];
          const priorityLayers = item.priority_layers || [];
          const candidatePatterns = item.candidate_patterns || [];
          const matchedPatternSymptoms = pattern.matched_symptoms || [];

          return (
            <div
              key={index}
              className={`card ${isExpanded ? "expanded" : ""} ${index === 0 ? "best-match-highlight" : ""}`}
              onClick={() => !isExpanded && toggleExpand(index)}
            >
              <div className="card-header">
                <div>
                  <span className="badge">{item.category}</span>
                  <h2>{item.name}</h2>
                </div>
                {isExpanded ? (
                  <FaChevronUp onClick={(e) => { e.stopPropagation(); toggleExpand(index); }} />
                ) : (
                  <FaChevronDown />
                )}
              </div>

              <p className="card-brief">
                <FaInfoCircle style={{ marginRight: "6px", color: "#81c784" }} />
                {item.explain?.reasoning || item.indications}
              </p>

              <div className="card-footer">
                <div>
                  Khớp: <span className="confidence-tag">{item.explain?.matched?.join(", ") || "N/A"}</span>
                </div>
                <div>
                  Độ tin cậy: <span className="confidence-tag">{typeof item.confidence === 'number' ? (item.confidence * 100).toFixed(1) + '%' : (item.confidence || "N/A")}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="card-details">
                  <div className="detail-section">
                    <h3><FaInfoCircle /> Giải thích kết quả</h3>
                    <div className="detail-content">{item.explain?.reasoning || "Chưa có lời giải thích."}</div>
                  </div>
                  {item.explain?.missing?.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Triệu chứng lâm sàng khác thường gặp (Thiếu)</h3>
                      <div className="detail-content missing-symptoms">
                        {item.explain.missing.map((sym, idx) => (
                          <span key={idx} className="missing-symptom-tag">{sym}</span>
                        ))}
                      </div>
                    </div>
                  )}


                  <div className="detail-section">
                    <h3><FaInfoCircle /> Tổng hợp biện chứng</h3>
                    <div className="detail-content">
                      <div className="meta-grid">
                        <div className="summary-item">
                          <span className="meta-label">Pattern</span>
                          <strong>{item.pattern || "Chưa xác định"}</strong>
                        </div>
                        <div className="summary-item">
                          <span className="meta-label">Phép trị</span>
                          <strong>{item.principle || "Chưa xác định"}</strong>
                        </div>
                        <div className="summary-item">
                          <span className="meta-label">Score</span>
                          <strong>{item.score}</strong>
                        </div>
                        <div className="summary-item">
                          <span className="meta-label">Coverage</span>
                          <strong>{typeof item.coverage === 'number' ? (item.coverage * 100).toFixed(1) + '%' : (item.coverage ?? "N/A")}</strong>
                        </div>
                      </div>
                    </div>
                  </div>


                  {item.modifier && Object.keys(item.modifier).some(k => item.modifier[k]) && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Modifier đã phát hiện</h3>
                      <div className="detail-content pill-list">
                        {Object.entries(item.modifier).filter(([k, v]) => v).map(([key, value]) => (
                          <div key={key} className="pill">
                            <strong>{formatModifier(key)}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {priorityLayers.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Priority logic</h3>
                      <div className="detail-content summary-grid">
                        {priorityLayers.map((layer) => (
                          <div key={layer.layer} className="summary-item">
                            <span className="meta-label">{layer.label}</span>
                            <strong>{formatAxis(layer.decision)}</strong>
                            <span>{layer.rationale}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {normalizedSymptoms.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Input đã chuẩn hóa</h3>
                      <div className="detail-content symptom-map">
                        {normalizedSymptoms.map((sym) => (
                          <div key={`${sym.symptom_id}-${sym.alias_used}`} className="symptom-map-item">
                            <strong>{sym.symptom_name}</strong>
                            <span>Alias match: {sym.alias_used}</span>
                            <span>Method: {formatMatchMethod(sym.match_method)}</span>
                            <span>Confidence: {sym.confidence}</span>
                            <span>Raw input: {(sym.raw_inputs || []).join(", ") || "N/A"}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {matchedPatternSymptoms.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Symptom đóng góp vào pattern</h3>
                      <div className="detail-content matched-list">
                        {matchedPatternSymptoms.map((sym) => (
                          <div key={`${sym.symptom_id}-${sym.symptom_name}`} className="matched-item">
                            <strong>{sym.symptom_name}</strong>
                            <span>Weight: {sym.weight}</span>
                            <span>Contribution: {sym.contribution}</span>
                            <span>Method: {formatMatchMethod(sym.match_method)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="detail-section">
                    <h3><FaLeaf /> Thành phần bài thuốc</h3>
                    <div className="detail-content">
                      {Array.isArray(item.composition) ? (
                        <div className="composition-grid">
                          {item.composition.map((herb, idx) => (
                            <div key={idx} className="herb-item">
                              <img 
                                src={herb.image || "https://placehold.co/60x60?text=No+Image"} 
                                alt={herb.name} 
                                onError={(e) => { e.target.src = "https://placehold.co/60x60?text=No+Image"; }}
                              />
                              <div className="herb-info">
                                <span className="herb-name">{herb.name}</span>
                                <span className="herb-dosage">
                                  {herb.dosage} {herb.unit}
                                  {herb.note && <span className="herb-note"> ({herb.note})</span>}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        item.composition
                      )}
                    </div>
                  </div>

                  <div className="detail-section">
                    <h3><FaFlask /> Cách dùng và liều lượng</h3>
                    <div className="detail-content">{item.usage}</div>
                  </div>

                  <div className="detail-section">
                    <h3><FaInfoCircle /> Công dụng đầy đủ</h3>
                    <div className="detail-content">{item.indications}</div>
                  </div>

                  {candidatePatterns.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Pattern ứng viên</h3>
                      <div className="detail-content candidate-patterns">
                        {candidatePatterns.map((candidate) => (
                          <div key={`${candidate.pattern_id}-${candidate.pattern_name}`} className="candidate-pattern-item">
                            <strong>{candidate.pattern_name}</strong>
                            <span>Score: {candidate.score}</span>
                            <span>Chief hits: {candidate.chief_hits}</span>
                            <span>Coverage: {candidate.coverage}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {item.reasoning_path?.length > 0 && (
                    <div className="detail-section">
                      <h3><FaInfoCircle /> Reasoning path</h3>
                      <div className="detail-content">
                        <ol className="reasoning-list">
                          {item.reasoning_path.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  )}

                  {item.clinical_warnings?.length > 0 && (
                    <div className="warning-box">
                      <strong><FaExclamationTriangle /> Lưu ý đặc biệt :</strong>
                      <ul>
                        {item.clinical_warnings.map((warning, i) => <li key={i}>{warning}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default App;
