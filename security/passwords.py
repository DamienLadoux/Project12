"""Hachage et vérification sécurisés des mots de passe."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
)


def hash_password(password: str) -> str:
    """Retourne un hachage Argon2id salé pour un mot de passe non vide."""
    if not isinstance(password, str) or not password:
        raise ValueError("Le mot de passe doit être une chaîne non vide.")

    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Indique si un mot de passe correspond au hachage Argon2id fourni."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False
