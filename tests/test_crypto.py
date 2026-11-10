"""Tests for the encryption used while text waits in the queue."""

import pytest
from cryptography.fernet import InvalidToken

from app.crypto import decrypt_text, encrypt_text


def test_text_survives_a_round_trip():
    text = "John Smith has chest pain. Naïve café — 痛み"

    assert decrypt_text(encrypt_text(text)) == text


def test_the_token_does_not_contain_the_text():
    assert "chest pain" not in encrypt_text("John Smith has chest pain")


def test_the_same_text_gives_a_different_token_each_time():
    # A random value is mixed in, so two identical notes cannot be recognised.
    assert encrypt_text("same note") != encrypt_text("same note")


def test_an_altered_token_is_rejected():
    token = encrypt_text("John Smith has chest pain")
    altered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")

    with pytest.raises(InvalidToken):
        decrypt_text(altered)
