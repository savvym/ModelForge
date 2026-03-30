import hashlib
import secrets


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "nta") -> tuple[str, str, str]:
    raw_key = f"{prefix}_{secrets.token_urlsafe(24)}"
    return raw_key, raw_key[:12], hash_api_key(raw_key)
