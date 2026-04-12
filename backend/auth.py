from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

# Configuration
SECRET_KEY = "DA_ATTT_SUPER_SECRET_KEY_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def _prepare_password(password: str) -> str:
    """
    Ensure the password is safe for bcrypt (max 72 bytes).
    1. Normalizes whitespace.
    2. Encodes to UTF-8 and truncates at 72 bytes.
    3. Decodes back safely to a string for passlib compatibility.
    """
    if not password:
        return ""
    # Normalize: strip whitespace
    cleaned = password.strip()
    # Encode and truncate at bcrypt's 72-byte limit
    password_bytes = cleaned.encode("utf-8")
    if len(password_bytes) > 72:
        # Truncate to 72 bytes and decode back to string (ignoring partial chars)
        password_bytes = password_bytes[:72]
        return password_bytes.decode("utf-8", errors="ignore")
    return cleaned

def verify_password(plain_password: str, hashed_password: str):
    """Verify a plain password against a hashed one using bcrypt."""
    return pwd_context.verify(_prepare_password(plain_password), hashed_password)

def get_password_hash(password: str):
    """Generate a bcrypt hash from a plain password."""
    return pwd_context.hash(_prepare_password(password))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token with a specific payload."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
