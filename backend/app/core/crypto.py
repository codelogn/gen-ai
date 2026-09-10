"""Fernet encryption for secrets this service must read back
(provider/backend API keys) — see docs/07-auth-and-api-keys.md for why this
is a different mechanism from the hashed application API keys."""

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _cipher() -> Fernet:
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set — required to encrypt/decrypt stored secrets. "
            "Generate one with Fernet.generate_key() and set it in .env."
        )
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> Optional[str]:
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None
