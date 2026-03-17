import base64
import hashlib
import hmac
import os

# Configuration constants
_SCHEME = "pbkdf2-sha256"
# Current OWASP recommended minimum for PBKDF2-SHA256 (as of 2024-2026)
_ITERATIONS = 600000 
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """
    Creates a secure, salted hash of the password using PBKDF2-HMAC-SHA256.
    Returns a string in the format: $scheme$iterations$salt$hash
    """
    # Use the raw UTF-8 encoded password as input to PBKDF2.
    password_bytes = password.encode("utf-8")
    salt = os.urandom(_SALT_BYTES)
    
    # Generate the derived key
    dk = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, _ITERATIONS)
    
    # Encode salt and derived key to Base64 for text storage
    salt_b64 = base64.b64encode(salt).decode()
    dk_b64 = base64.b64encode(dk).decode()
    
    return f"${_SCHEME}${_ITERATIONS}${salt_b64}${dk_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a password against a stored hash. 
    It automatically adapts to the number of iterations stored in the hash string.
    """
    try:
        parts = password_hash.split("$")
        # Format: $scheme$iterations$salt_b64$hash_b64
        if len(parts) != 5 or parts[1] != _SCHEME:
            return False
            
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        expected = base64.b64decode(parts[4])
    except (ValueError, IndexError, base64.binascii.Error):
        return False
        
    # Use the same UTF-8 encoded password as input to PBKDF2.
    password_bytes = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, iterations)
    
    # Use hmac.compare_digest to prevent timing attacks
    return hmac.compare_digest(dk, expected)


def needs_rehash(password_hash: str) -> bool:
    """
    Checks if the password hash needs to be updated to the latest security standards.
    Returns True if the iteration count is lower than the current _ITERATIONS constant.
    """
    try:
        parts = password_hash.split("$")
        if len(parts) != 5:
            return True
            
        current_iterations = int(parts[2])
        # Compare iterations stored in the hash with the current system requirement
        return current_iterations < _ITERATIONS
    except (ValueError, IndexError):
        return True