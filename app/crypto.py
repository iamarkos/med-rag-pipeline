"""Encrypting document text while it waits in the queue.

The API encrypts the extracted text before handing it to Redis, and the worker
decrypts it. Anyone who can read Redis sees only ciphertext.

This uses Fernet from the `cryptography` library: symmetric encryption (one
secret key does both jobs) that also detects tampering. The key comes from the
TEXT_ENCRYPTION_KEY environment variable and is never stored with the data.
"""

from cryptography.fernet import Fernet

from app.config import get_text_encryption_key


def _build_cipher() -> Fernet:
    try:
        return Fernet(get_text_encryption_key())
    except ValueError:
        # Deliberately says nothing about the value that was rejected.
        raise RuntimeError(
            "TEXT_ENCRYPTION_KEY is not a valid key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from None


# Built when this module is first imported, so a missing or malformed key stops
# the API and the worker at startup instead of at the first upload.
_cipher = _build_cipher()


def encrypt_text(text: str) -> str:
    """Turn text into an unreadable token that is safe to put in the queue."""
    return _cipher.encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    """Turn a token from encrypt_text back into the original text.

    Raises cryptography.fernet.InvalidToken if the token was not made with this
    key or has been altered.
    """
    return _cipher.decrypt(token.encode("ascii")).decode("utf-8")
