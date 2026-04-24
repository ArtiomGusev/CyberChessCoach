import base64
import hashlib
import hmac
import os

_SCHEME_V1 = "pbkdf2-sha256"       # legacy: normalisation = raw SHA-256 digest
_SCHEME = "pbkdf2-sha256-v2"        # current: normalisation = 1-iter PBKDF2
_ITERATIONS = 600000
_SALT_BYTES = 16
_NORM_SALT = b"auth.normalization.static.salt"


def _normalize_password(password: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _NORM_SALT, 1)


def _normalize_password_v1(password: str) -> bytes:
    """Legacy normalisation path used by hashes stored before the v2 scheme."""
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
        if len(parts) != 5:
            return False
        scheme = parts[1]
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        expected = base64.b64decode(parts[4])
    except (ValueError, IndexError, base64.binascii.Error):
        return False

    if scheme == _SCHEME:
        normalized = _normalize_password(password)
    elif scheme == _SCHEME_V1:
        normalized = _normalize_password_v1(password)
    else:
        return False

    dk = hashlib.pbkdf2_hmac("sha256", normalized, salt, iterations)
    return hmac.compare_digest(dk, expected)


def needs_rehash(password_hash: str) -> bool:
    try:
        parts = password_hash.split("$")
        if len(parts) != 5:
            return True
        if parts[1] != _SCHEME:
            return True
        return int(parts[2]) < _ITERATIONS
    except (ValueError, IndexError):
        return True
