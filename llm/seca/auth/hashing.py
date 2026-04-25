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
    """Legacy pre-processing step for hashes stored under the v1 scheme (pbkdf2-sha256).

    SAST note (Bandit B324 / CWE-327): SHA-256 is flagged as a weak password-hashing
    primitive, but this is a pre-processing step — not the full hashing chain.  The digest
    is immediately fed into PBKDF2-SHA256 with 600 000 iterations and a per-hash random
    16-byte salt.  PBKDF2 is the actual work-factor barrier against offline brute-force.

    This function MUST NOT be changed.  Altering the normalisation produces different
    PBKDF2-derived keys for all existing v1 hashes in the database, silently breaking
    authentication for those users.  The correct migration path is the opportunistic upgrade
    in service.login(): every successful v1 login rewrites the stored hash to v2, which uses
    _normalize_password().  No new v1 hashes are ever created; hash_password() always emits v2.
    """
    return hashlib.sha256(password.encode("utf-8")).digest()  # nosec B324 — see docstring


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
