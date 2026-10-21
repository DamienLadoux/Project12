"""Tests unitaires des fonctions de sécurité des mots de passe."""

import pytest

from security.passwords import hash_password, verify_password


def test_hash_password_returns_a_hash_not_the_plain_password():
    """Le hachage stockable ne contient pas le mot de passe en clair."""
    password = "MotDePasseTest!2026"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")


def test_verify_password_accepts_the_correct_password():
    """Le mot de passe d'origine est accepté par son hachage."""
    password_hash = hash_password("MotDePasseTest!2026")

    assert verify_password("MotDePasseTest!2026", password_hash)


def test_verify_password_rejects_an_incorrect_password():
    """Un mot de passe erroné ne valide pas le hachage enregistré."""
    password_hash = hash_password("MotDePasseTest!2026")

    assert not verify_password("MotDePasseIncorrect!2026", password_hash)


def test_hash_password_rejects_an_empty_password():
    """Un mot de passe vide ne peut pas être enregistré."""
    with pytest.raises(ValueError, match="non vide"):
        hash_password("")
