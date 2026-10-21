"""Point d'entrée en ligne de commande de l'application Epic Events."""

import argparse
import getpass
import os

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import create_database_engine
from security.tokens import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    TokenConfigurationError,
)
from services.auth_session import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
    get_current_actor,
    login,
    logout,
)


def build_parser() -> argparse.ArgumentParser:
    """Déclare les commandes d'authentification disponibles."""
    parser = argparse.ArgumentParser(
        prog="epicevents",
        description="CRM en ligne de commande d'Epic Events",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser(
        "login",
        help="ouvrir une session persistante",
    )
    login_parser.add_argument(
        "identifier",
        nargs="?",
        help="numéro d'employé ou adresse e-mail",
    )
    subparsers.add_parser("logout", help="fermer la session locale")
    subparsers.add_parser("whoami", help="afficher le collaborateur connecté")

    return parser


def _jwt_secret() -> str:
    """Lit le secret sans fournir de valeur de repli non sécurisée."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise TokenConfigurationError(
            "La variable JWT_SECRET est absente du fichier .env."
        )
    return secret


def _run_login(identifier: str | None) -> None:
    """Demande les identifiants puis enregistre la nouvelle session."""
    entered_identifier = identifier or input(
        "Numéro d'employé ou e-mail : "
    ).strip()
    password = getpass.getpass("Mot de passe : ")
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            employee = login(
                session,
                entered_identifier,
                password,
                _jwt_secret(),
            )
            identity_label = (
                f"{employee.full_name} ({employee.role.name})"
            )
    finally:
        engine.dispose()

    print(f"Connexion réussie : {identity_label}.")


def _run_whoami() -> None:
    """Valide le jeton puis affiche le compte actuellement connecté."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            employee = get_current_actor(session, _jwt_secret())
            print(
                f"{employee.full_name} | {employee.employee_number} "
                f"| {employee.role.name}"
            )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Exécute une commande et transforme les erreurs en messages CLI."""
    load_dotenv()
    arguments = build_parser().parse_args(argv)

    try:
        if arguments.command == "login":
            _run_login(arguments.identifier)
        elif arguments.command == "logout":
            if logout():
                print("Déconnexion réussie.")
            else:
                print("Aucune session active.")
        elif arguments.command == "whoami":
            _run_whoami()
    except (
        AuthenticationRequiredError,
        ExpiredAccessTokenError,
        InvalidAccessTokenError,
        InvalidCredentialsError,
        TokenConfigurationError,
        ValueError,
    ) as error:
        print(f"Erreur : {error}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
