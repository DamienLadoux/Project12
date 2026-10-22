"""Stockage local et persistant du jeton d'accès."""

import os
import tempfile
from pathlib import Path

TOKEN_FILE_ENVIRONMENT_VARIABLE = "EPIC_EVENTS_TOKEN_FILE"


class StoredTokenNotFoundError(FileNotFoundError):
    """Levée lorsqu'aucune session persistante n'est disponible."""


def default_token_path() -> Path:
    """Choisit un emplacement utilisateur compatible Windows et Unix."""
    configured_path = os.getenv(TOKEN_FILE_ENVIRONMENT_VARIABLE)
    if configured_path:
        return Path(configured_path).expanduser()

    if os.name == "nt":
        base_directory = Path(
            os.getenv("LOCALAPPDATA", str(Path.home()))
        )
        return base_directory / "EpicEvents" / "access_token"

    state_directory = os.getenv("XDG_STATE_HOME")
    base_directory = (
        Path(state_directory).expanduser()
        if state_directory
        else Path.home() / ".local" / "state"
    )
    return base_directory / "epic-events" / "access_token"


def save_token(token: str, path: Path | None = None) -> Path:
    """Enregistre le jeton atomiquement dans un fichier privé."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Le jeton à enregistrer est invalide.")

    token_path = path or default_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=token_path.parent,
            prefix=".access_token_",
            delete=False,
        ) as temporary_file:
            temporary_file.write(token.strip())
            temporary_path = Path(temporary_file.name)

        temporary_path.chmod(0o600)
        temporary_path.replace(token_path)
        token_path.chmod(0o600)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return token_path


def load_token(path: Path | None = None) -> str:
    """Lit le jeton stocké ou signale l'absence de session."""
    token_path = path or default_token_path()
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise StoredTokenNotFoundError(
            "Aucune session active. Utilisez la commande login."
        ) from error

    if not token:
        raise StoredTokenNotFoundError(
            "Aucune session active. Utilisez la commande login."
        )

    return token


def delete_token(path: Path | None = None) -> bool:
    """Supprime le jeton local et indique s'il existait."""
    token_path = path or default_token_path()
    try:
        token_path.unlink()
    except FileNotFoundError:
        return False

    return True
