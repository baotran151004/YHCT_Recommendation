import React, { useState } from "react";
import "./App.css";
import { FaSearch, FaLeaf, FaFlask, FaInfoCircle, FaExclamationTriangle, FaChevronDown, FaChevronUp } from "react-icons/fa";

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
      const res = await fetch(`http://127.0.0.1:8000/expert-system/recommend?symptom=${encodeURIComponent(symptom)}`);
      const result = await res.json();
      
      if (Array.isArray(result)) {
        setData(result);
      } else {
        setData([]);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      // alert("Lỗi kết nối tới máy chủ!");
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (index) => {
    if (expandedId === index) {
      setExpandedId(null);
    } else {
      setExpandedId(index);
    }
  };

  return (
    <div className="container">
      
      {/* HEADER */}
      <header className="header">
        <h1>🌿 YHCT Expert</h1>
        <p>Hệ thống hỗ trợ chẩn trị & Gợi ý bài thuốc Đông y</p>
      </header>

      {/* SEARCH */}
      <div className="search-wrapper">
        <FaSearch className="search-icon" />
        <input
          value={symptom}
          onChange={(e) => setSymptom(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Ví dụ: đau đầu, chóng mặt, sợ lạnh..."
        />
        <button onClick={handleSearch} disabled={loading}>
          Phân tích
        </button>
      </div>

      {/* STATES */}
      {loading && (
        <div className="loader-container">
          <div className="spinner"></div>
          <p>Đang phân tích triệu chứng...</p>
        </div>
      )}

      {!loading && symptom && data.length === 0 && (
        <div className="empty" style={{ opacity: 0.6 }}>
          <p>Không tìm thấy bài thuốc phù hợp. Vui lòng thử lại với triệu chứng khác.</p>
        </div>
      )}

      {/* RESULTS */}
      <div className="results-list">
        {data.map((item, index) => {
          const isExpanded = expandedId === index;
          
          return (
            <div
              key={index}
              className={`card ${isExpanded ? "expanded" : ""}`}
              onClick={() => !isExpanded && toggleExpand(index)}
            >
              <div className="card-header">
                <div>
                  <span className="badge">{item.category}</span>
                  <h2>{item.name}</h2>
                </div>
                {isExpanded ? <FaChevronUp onClick={(e) => { e.stopPropagation(); toggleExpand(index); }} /> : <FaChevronDown />}
              </div>

              <p className="card-brief">
                <FaInfoCircle style={{ marginRight: '6px', color: '#81c784' }} />
                {item.indications.length > 120 ? item.indications.substring(0, 120) + "..." : item.indications}
              </p>

              {/* DETAILED VIEW */}
              {isExpanded && (
                <div className="card-details">
                  <div className="detail-section">
                    <h3><FaLeaf /> Thành phần bài thuốc</h3>
                    <div className="detail-content">
                      {Array.isArray(item.composition) ? (
                        <div className="composition-grid">
                          {item.composition.map((herb, idx) => (
                            <div key={idx} className="composition-item">
                              <span className="herb-name">{herb.name}</span>
                              <span className="herb-dosage">
                                {herb.dosage} {herb.unit}
                                {herb.note && <span className="herb-note"> ({herb.note})</span>}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        item.composition
                      )}
                    </div>
                  </div>

                  <div className="detail-section">
                    <h3><FaFlask /> Cách dùng & Liều lượng</h3>
                    <div className="detail-content">{item.usage}</div>
                  </div>

                  <div className="detail-section">
                    <h3><FaInfoCircle /> Công dụng đầy đủ</h3>
                    <div className="detail-content">{item.indications}</div>
                  </div>

                  {item.clinical_warnings?.length > 0 && (
                    <div className="warning-box">
                      <strong><FaExclamationTriangle /> Lưu ý đặc biệt:</strong>
                      <ul>
                        {item.clinical_warnings.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div className="card-footer">
                <div>
                  Khớp: <span className="confidence-tag">{item.matched_symptoms?.join(", ") || "N/A"}</span>
                </div>
                <div>
                  Độ tin cậy: <span className="confidence-tag">{item.confidence}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default App;