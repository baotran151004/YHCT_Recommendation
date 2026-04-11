import re
from fastapi import HTTPException, status
import logging

# Thiết lập Logger an toàn
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security_audit")

# Tự động bắt các keyword injection phổ biến ở đầu vào
SQLI_PATTERNS = [
    r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b)",
    r"(--|#|\/\*|\*\/)",
    r"(\bor\b\s+1\s*=\s*1)",
    r"(\bxor\b\s+1\s*=\s*1)",
    r"(\band\b\s+1\s*=\s*1)"
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
