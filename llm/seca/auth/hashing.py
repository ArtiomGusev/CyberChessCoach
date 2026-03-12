import base64
import hashlib
import hmac
import os

_SCHEME = "pbkdf2-sha256"
_ITERATIONS = 260000  # OWASP recommended minimum for PBKDF2-SHA256
_SALT_BYTES = 16


def _normalize_password(password: str) -> bytes:
    """
    Normalize password to <=72 bytes for bcrypt compatibility.
    Kept as-is so verify_password remains compatible with existing stored hashes.
    """
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    normalized = _normalize_password(password)
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", normalized, salt, _ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode()
    dk_b64 = base64.b64encode(dk).decode()
    return f"${_SCHEME}${_ITERATIONS}${salt_b64}${dk_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        parts = password_hash.split("$")
        # Expected format: $pbkdf2-sha256$<iterations>$<salt_b64>$<hash_b64>
        if len(parts) != 5 or parts[1] != _SCHEME:
            return False
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        expected = base64.b64decode(parts[4])
    except (ValueError, IndexError):
        return False
    normalized = _normalize_password(password)
    dk = hashlib.pbkdf2_hmac("sha256", normalized, salt, iterations)
    return hmac.compare_digest(dk, expected)
