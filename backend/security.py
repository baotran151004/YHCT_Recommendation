import re
from fastapi import HTTPException, status
import logging

# Thiết lập Logger an toàn
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security_audit")

# Tự động bắt các keyword injection phổ biến ở đầu vào
SQLI_PATTERNS = [
    # 1. Các lệnh thao tác dữ liệu cơ bản (DML/DDL)
    r"\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|DECLARE)\b",
    
    # 2. Xử lý các phép so sánh Tautology (VD: OR 1=1, ' OR 'a'='a, AND "b"="b")
    r"\b(OR|AND|XOR)\b\s*['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?",
    
    # 3. Phát hiện việc đóng chuỗi sớm (móc ngoặc đơn/kép) rồi thêm điều kiện logic (VD: ' OR, " OR)
    r"['\"]\s*\b(OR|AND|XOR)\b",
    
    # 4. Ký tự comment trong SQL (-- hoặc /* */)
    r"(--|#|\/\*|\*\/)",
    
    # 5. Ngăn chặn đa câu lệnh (; DROP TABLE)
    r";\s*\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|DECLARE)\b"
]

def sanitize_and_check_input(symptom: str) -> str:
    if not symptom:
        return symptom
        
    if len(symptom) > 255:
        logger.warning(f"[SECURITY] Input length exceeded 255 chars")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input too long.")

    # Convert to uppercase for comparison or use regex ignorace case
    suspicious_found = False
    for pattern in SQLI_PATTERNS:
        if re.search(pattern, symptom, re.IGNORECASE):
            suspicious_found = True
            break
            
    if suspicious_found:
        logger.error(f"[SECURITY ALERT] Malicious input detected: {symptom}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Malicious input detected. Operation blocked."
        )

    # Nếu an toàn
    return symptom
