"""Validations réutilisables pour les données saisies dans les services."""

from decimal import Decimal, InvalidOperation


def required_text(value: str, error_message: str) -> str:
    """Retourne un texte nettoyé ou lève une erreur de validation."""
    if not isinstance(value, str) or not (normalized_value := value.strip()):
        raise ValueError(error_message)

    return normalized_value


def normalize_email(email: str) -> str:
    """Valide sommairement et normalise une adresse e-mail."""
    normalized_email = required_text(
        email,
        "L'adresse e-mail est obligatoire.",
    ).lower()
    if "@" not in normalized_email:
        raise ValueError("L'adresse e-mail est invalide.")

    return normalized_email


def optional_text(value: str | None) -> str | None:
    """Nettoie un texte facultatif et transforme une valeur vide en ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("La valeur doit être une chaîne de caractères.")

    return value.strip() or None


def nonnegative_decimal(value: object, field_name: str) -> Decimal:
    """Convertit une valeur en montant décimal positif ou nul."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} doit être un montant valide.")

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"{field_name} doit être un montant valide."
        ) from None

    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field_name} doit être positif ou nul.")

    return amount
