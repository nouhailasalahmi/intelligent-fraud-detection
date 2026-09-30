from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import hashlib
import os

from api.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    USE_PASSLIB = True
except Exception:
    USE_PASSLIB = False

PASSWORD_SALT = "B4NK_FR4UD_D3T3CT10N_P4SSW0RD_S4LT_2026"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre son empreinte hachée."""
    if not plain_password or not hashed_password:
        return False
    if USE_PASSLIB and hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            pass
    # Fallback SHA-256 salé
    salted = f"{PASSWORD_SALT}_{plain_password}"
    candidate_hash = hashlib.sha256(salted.encode("utf-8")).hexdigest()
    return candidate_hash == hashed_password or hashed_password == plain_password


def get_password_hash(password: str) -> str:

    if USE_PASSLIB:
        try:
            return pwd_context.hash(password)
        except Exception:
            pass
    salted = f"{PASSWORD_SALT}_{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Crée un token JWT signé."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
