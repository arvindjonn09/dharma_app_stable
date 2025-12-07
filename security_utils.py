import os
from typing import Optional

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore


def _get_cipher() -> Optional["Fernet"]:
    """
    Return a Fernet cipher using env var FERNET_KEY (base64 urlsafe key).
    If cryptography or key is unavailable, return None and passthrough values.
    """
    if Fernet is None:
        return None
    key = os.getenv("FERNET_KEY")
    if not key:
        return None
    try:
        return Fernet(key)
    except Exception:
        return None


def encrypt_field(value: str) -> str:
    if not value:
        return value
    cipher = _get_cipher()
    if not cipher:
        return value
    try:
        return cipher.encrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value


def decrypt_field(value: str) -> str:
    if not value:
        return value
    cipher = _get_cipher()
    if not cipher:
        return value
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value
