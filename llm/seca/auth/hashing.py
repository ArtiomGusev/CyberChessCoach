import hashlib
from passlib.context import CryptContext

# Use pbkdf2_sha256 to avoid bcrypt backend issues on Windows.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _normalize_password(password: str) -> bytes:
    """
    Normalize password to <=72 bytes for bcrypt
    by hashing with SHA-256 first.
    """
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return pwd_context.hash(_normalize_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(_normalize_password(password), password_hash)
