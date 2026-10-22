"""Point d'entrée en ligne de commande de l'application Epic Events."""

import argparse
import getpass
import os
from datetime import date, datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cli.presentation import (
    display_clients,
    display_contracts,
    display_employees,
    display_events,
    print_error,
    print_info,
    print_success,
)
from database import create_database_engine
from models import Client, Contract, Employee, Event
from monitoring import (
    capture_contract_signature,
    capture_login,
    configure_monitoring,
    set_actor_context,
)
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
from services.authorization import AuthorizationError
from services.client_service import create_client, update_client
from services.contract_service import create_contract, update_contract
from services.employee_service import (
    create_employee,
    delete_employee,
    update_employee,
)
from services.event_service import (
    assign_event_support,
    create_event,
    update_event,
)
from services.query_service import (
    list_clients,
    list_contracts,
    list_employees,
    list_events,
)


AUTHENTICATION_COMMANDS = frozenset({"login", "logout", "whoami"})


class EntityNotFoundError(ValueError):
    """Levée lorsqu'un identifiant CLI ne correspond à aucune ligne."""


def _positive_integer(value: str) -> int:
    """Valide un identifiant strictement positif fourni dans le terminal."""
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "un entier strictement positif est attendu"
        ) from error
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(
            "un entier strictement positif est attendu"
        )
    return parsed_value


def _nonnegative_integer(value: str) -> int:
    """Valide un nombre entier positif ou nul."""
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "un entier positif ou nul est attendu"
        ) from error
    if parsed_value < 0:
        raise argparse.ArgumentTypeError(
            "un entier positif ou nul est attendu"
        )
    return parsed_value


def _iso_date(value: str) -> date:
    """Convertit une date ISO fournie par argparse."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "format attendu : AAAA-MM-JJ"
        ) from error


def _iso_datetime(value: str) -> datetime:
    """Convertit une date/heure ISO contenant obligatoirement un fuseau."""
    try:
        parsed_value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "format ISO attendu, par exemple 2026-11-01T09:00:00+01:00"
        ) from error

    if parsed_value.tzinfo is None:
        raise argparse.ArgumentTypeError(
            "la date/heure doit contenir un fuseau, par exemple +01:00"
        )
    return parsed_value


def _add_authentication_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Ajoute login, logout et whoami au parseur principal."""
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


def _add_employee_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Ajoute les commandes administratives des collaborateurs."""
    employees = subparsers.add_parser(
        "employees",
        help="gérer les collaborateurs (gestion)",
    )
    actions = employees.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="lister les collaborateurs")

    create_parser = actions.add_parser("create", help="créer un collaborateur")
    create_parser.add_argument("--number", required=True)
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument(
        "--role",
        required=True,
        choices=("GESTION", "COMMERCIAL", "SUPPORT"),
    )

    update_parser = actions.add_parser(
        "update",
        help="modifier un collaborateur",
    )
    update_parser.add_argument("employee_id", type=_positive_integer)
    update_parser.add_argument("--number", default=argparse.SUPPRESS)
    update_parser.add_argument("--name", default=argparse.SUPPRESS)
    update_parser.add_argument("--email", default=argparse.SUPPRESS)
    update_parser.add_argument(
        "--role",
        choices=("GESTION", "COMMERCIAL", "SUPPORT"),
        default=argparse.SUPPRESS,
    )
    update_parser.add_argument(
        "--change-password",
        action="store_true",
        help=(
            "demander un nouveau mot de passe sans l'exposer dans "
            "l'historique"
        ),
    )

    delete_parser = actions.add_parser(
        "delete",
        help="supprimer un collaborateur",
    )
    delete_parser.add_argument("employee_id", type=_positive_integer)


def _add_client_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Ajoute les commandes de consultation et de gestion des clients."""
    clients = subparsers.add_parser(
        "clients",
        help="consulter et gérer les clients",
    )
    actions = clients.add_subparsers(dest="action", required=True)

    list_parser = actions.add_parser("list", help="lister les clients")
    list_parser.add_argument("--mine", action="store_true")

    create_parser = actions.add_parser("create", help="créer un client")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--phone")
    create_parser.add_argument("--company")

    update_parser = actions.add_parser("update", help="modifier un client")
    update_parser.add_argument("client_id", type=_positive_integer)
    update_parser.add_argument("--name", default=argparse.SUPPRESS)
    update_parser.add_argument("--email", default=argparse.SUPPRESS)
    update_parser.add_argument(
        "--last-contact",
        type=_iso_date,
        default=argparse.SUPPRESS,
    )
    phone_group = update_parser.add_mutually_exclusive_group()
    phone_group.add_argument("--phone", default=argparse.SUPPRESS)
    phone_group.add_argument(
        "--clear-phone",
        dest="phone",
        action="store_const",
        const=None,
        default=argparse.SUPPRESS,
    )
    company_group = update_parser.add_mutually_exclusive_group()
    company_group.add_argument("--company", default=argparse.SUPPRESS)
    company_group.add_argument(
        "--clear-company",
        dest="company",
        action="store_const",
        const=None,
        default=argparse.SUPPRESS,
    )


def _add_contract_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Ajoute les commandes de consultation et de gestion des contrats."""
    contracts = subparsers.add_parser(
        "contracts",
        help="consulter et gérer les contrats",
    )
    actions = contracts.add_subparsers(dest="action", required=True)

    list_parser = actions.add_parser("list", help="lister les contrats")
    list_parser.add_argument("--mine", action="store_true")
    list_parser.add_argument("--unsigned", action="store_true")
    list_parser.add_argument("--unpaid", action="store_true")

    create_parser = actions.add_parser("create", help="créer un contrat")
    create_parser.add_argument("client_id", type=_positive_integer)
    create_parser.add_argument("--total", required=True)
    create_parser.add_argument("--remaining", required=True)
    create_parser.add_argument("--signed", action="store_true")

    update_parser = actions.add_parser("update", help="modifier un contrat")
    update_parser.add_argument("contract_id", type=_positive_integer)
    update_parser.add_argument(
        "--client-id",
        type=_positive_integer,
        default=argparse.SUPPRESS,
    )
    update_parser.add_argument("--total", default=argparse.SUPPRESS)
    update_parser.add_argument("--remaining", default=argparse.SUPPRESS)
    signature_group = update_parser.add_mutually_exclusive_group()
    signature_group.add_argument(
        "--signed",
        dest="is_signed",
        action="store_true",
        default=argparse.SUPPRESS,
    )
    signature_group.add_argument(
        "--unsigned",
        dest="is_signed",
        action="store_false",
        default=argparse.SUPPRESS,
    )


def _add_event_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Ajoute les commandes de consultation et de gestion des événements."""
    events = subparsers.add_parser(
        "events",
        help="consulter et gérer les événements",
    )
    actions = events.add_subparsers(dest="action", required=True)

    list_parser = actions.add_parser("list", help="lister les événements")
    list_parser.add_argument("--mine", action="store_true")
    list_parser.add_argument("--without-support", action="store_true")

    create_parser = actions.add_parser("create", help="créer un événement")
    create_parser.add_argument("contract_id", type=_positive_integer)
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--start", type=_iso_datetime, required=True)
    create_parser.add_argument("--end", type=_iso_datetime, required=True)
    create_parser.add_argument("--location", required=True)
    create_parser.add_argument(
        "--attendees",
        type=_nonnegative_integer,
        required=True,
    )
    create_parser.add_argument("--notes")

    update_parser = actions.add_parser("update", help="modifier un événement")
    update_parser.add_argument("event_id", type=_positive_integer)
    update_parser.add_argument(
        "--contract-id",
        type=_positive_integer,
        default=argparse.SUPPRESS,
    )
    update_parser.add_argument("--name", default=argparse.SUPPRESS)
    update_parser.add_argument(
        "--start",
        type=_iso_datetime,
        default=argparse.SUPPRESS,
    )
    update_parser.add_argument(
        "--end",
        type=_iso_datetime,
        default=argparse.SUPPRESS,
    )
    update_parser.add_argument("--location", default=argparse.SUPPRESS)
    update_parser.add_argument(
        "--attendees",
        type=_nonnegative_integer,
        default=argparse.SUPPRESS,
    )
    notes_group = update_parser.add_mutually_exclusive_group()
    notes_group.add_argument("--notes", default=argparse.SUPPRESS)
    notes_group.add_argument(
        "--clear-notes",
        dest="notes",
        action="store_const",
        const=None,
        default=argparse.SUPPRESS,
    )

    assign_parser = actions.add_parser(
        "assign-support",
        help="affecter un membre du support (gestion)",
    )
    assign_parser.add_argument("event_id", type=_positive_integer)
    support_group = assign_parser.add_mutually_exclusive_group(required=True)
    support_group.add_argument("--support-id", type=_positive_integer)
    support_group.add_argument("--clear", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    """Déclare toutes les commandes de l'application."""
    parser = argparse.ArgumentParser(
        prog="epicevents",
        description="CRM en ligne de commande d'Epic Events",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_authentication_commands(subparsers)
    _add_employee_commands(subparsers)
    _add_client_commands(subparsers)
    _add_contract_commands(subparsers)
    _add_event_commands(subparsers)
    return parser


def _jwt_secret() -> str:
    """Lit le secret sans fournir de valeur de repli non sécurisée."""
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise TokenConfigurationError(
            "La variable JWT_SECRET est absente du fichier .env."
        )
    return secret


def _get_entity(
    session: Session,
    model: type[Any],
    entity_id: int,
    label: str,
) -> Any:
    """Charge une entité par sa clé primaire ou lève une erreur CLI."""
    entity = session.get(model, entity_id)
    if entity is None:
        raise EntityNotFoundError(
            f"{label} avec l'identifiant {entity_id} introuvable."
        )
    return entity


def _provided_arguments(
    arguments: argparse.Namespace,
    mapping: dict[str, str],
) -> dict[str, object]:
    """Transforme les options saisies en arguments destinés au service."""
    return {
        service_name: getattr(arguments, cli_name)
        for cli_name, service_name in mapping.items()
        if hasattr(arguments, cli_name)
    }


def _dispatch_employee_command(
    session: Session,
    actor: Employee,
    arguments: argparse.Namespace,
) -> None:
    if arguments.action == "list":
        display_employees(list_employees(session, actor))
    elif arguments.action == "create":
        password = getpass.getpass("Mot de passe initial : ")
        employee = create_employee(
            session,
            actor,
            arguments.number,
            arguments.name,
            arguments.email,
            password,
            arguments.role,
        )
        print_success(
            f"Collaborateur créé avec l'identifiant {employee.id}."
        )
    elif arguments.action == "update":
        employee = _get_entity(
            session,
            Employee,
            arguments.employee_id,
            "Collaborateur",
        )
        changes = _provided_arguments(
            arguments,
            {
                "number": "employee_number",
                "name": "full_name",
                "email": "email",
                "role": "role_name",
            },
        )
        if arguments.change_password:
            changes["password"] = getpass.getpass("Nouveau mot de passe : ")
        update_employee(session, actor, employee, **changes)
        print_success("Collaborateur modifié.")
    elif arguments.action == "delete":
        employee = _get_entity(
            session,
            Employee,
            arguments.employee_id,
            "Collaborateur",
        )
        delete_employee(session, actor, employee)
        print_success("Collaborateur supprimé.")


def _dispatch_client_command(
    session: Session,
    actor: Employee,
    arguments: argparse.Namespace,
) -> None:
    if arguments.action == "list":
        clients = list_clients(session, actor, mine_only=arguments.mine)
        display_clients(clients)
    elif arguments.action == "create":
        client = create_client(
            session,
            actor,
            arguments.name,
            arguments.email,
            phone=arguments.phone,
            company_name=arguments.company,
        )
        print_success(f"Client créé avec l'identifiant {client.id}.")
    elif arguments.action == "update":
        client = _get_entity(
            session,
            Client,
            arguments.client_id,
            "Client",
        )
        changes = _provided_arguments(
            arguments,
            {
                "name": "full_name",
                "email": "email",
                "phone": "phone",
                "company": "company_name",
                "last_contact": "last_contact_at",
            },
        )
        update_client(session, actor, client, **changes)
        print_success("Client modifié.")


def _dispatch_contract_command(
    session: Session,
    actor: Employee,
    arguments: argparse.Namespace,
) -> Contract | None:
    if arguments.action == "list":
        contracts = list_contracts(
            session,
            actor,
            mine_only=arguments.mine,
            unsigned_only=arguments.unsigned,
            unpaid_only=arguments.unpaid,
        )
        display_contracts(contracts)
    elif arguments.action == "create":
        client = _get_entity(
            session,
            Client,
            arguments.client_id,
            "Client",
        )
        contract = create_contract(
            session,
            actor,
            client,
            arguments.total,
            arguments.remaining,
            is_signed=arguments.signed,
        )
        print_success(f"Contrat créé avec l'identifiant {contract.id}.")
        if contract.is_signed:
            return contract
    elif arguments.action == "update":
        contract = _get_entity(
            session,
            Contract,
            arguments.contract_id,
            "Contrat",
        )
        changes = _provided_arguments(
            arguments,
            {
                "total": "total_amount",
                "remaining": "remaining_amount",
                "is_signed": "is_signed",
            },
        )
        if hasattr(arguments, "client_id"):
            changes["client"] = _get_entity(
                session,
                Client,
                arguments.client_id,
                "Client",
            )
        was_signed = contract.is_signed
        update_contract(session, actor, contract, **changes)
        print_success("Contrat modifié.")
        if not was_signed and contract.is_signed:
            return contract

    return None


def _dispatch_event_command(
    session: Session,
    actor: Employee,
    arguments: argparse.Namespace,
) -> None:
    if arguments.action == "list":
        events = list_events(
            session,
            actor,
            mine_only=arguments.mine,
            without_support_only=arguments.without_support,
        )
        display_events(events)
    elif arguments.action == "create":
        contract = _get_entity(
            session,
            Contract,
            arguments.contract_id,
            "Contrat",
        )
        event = create_event(
            session,
            actor,
            contract,
            arguments.name,
            arguments.start,
            arguments.end,
            arguments.location,
            arguments.attendees,
            notes=arguments.notes,
        )
        print_success(f"Événement créé avec l'identifiant {event.id}.")
    elif arguments.action == "update":
        event = _get_entity(
            session,
            Event,
            arguments.event_id,
            "Événement",
        )
        changes = _provided_arguments(
            arguments,
            {
                "name": "name",
                "start": "start_date",
                "end": "end_date",
                "location": "location",
                "attendees": "attendees",
                "notes": "notes",
            },
        )
        if hasattr(arguments, "contract_id"):
            changes["contract"] = _get_entity(
                session,
                Contract,
                arguments.contract_id,
                "Contrat",
            )
        update_event(session, actor, event, **changes)
        print_success("Événement modifié.")
    elif arguments.action == "assign-support":
        event = _get_entity(
            session,
            Event,
            arguments.event_id,
            "Événement",
        )
        support = (
            None
            if arguments.clear
            else _get_entity(
                session,
                Employee,
                arguments.support_id,
                "Collaborateur support",
            )
        )
        assign_event_support(session, actor, event, support)
        print_success("Affectation du support modifiée.")


def _dispatch_business_command(
    session: Session,
    actor: Employee,
    arguments: argparse.Namespace,
) -> Contract | None:
    """Route une commande analysée vers le service métier correspondant."""
    if arguments.command == "employees":
        _dispatch_employee_command(session, actor, arguments)
    elif arguments.command == "clients":
        _dispatch_client_command(session, actor, arguments)
    elif arguments.command == "contracts":
        return _dispatch_contract_command(session, actor, arguments)
    elif arguments.command == "events":
        _dispatch_event_command(session, actor, arguments)

    return None


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
            identity_label = f"{employee.full_name} ({employee.role.name})"
            capture_login(employee)
    finally:
        engine.dispose()
    print_success(f"Connexion réussie : {identity_label}.")


def _run_whoami() -> None:
    """Valide le jeton puis affiche le compte actuellement connecté."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            employee = get_current_actor(session, _jwt_secret())
            set_actor_context(employee)
            print_info(
                f"{employee.full_name} | {employee.employee_number} "
                f"| {employee.role.name}"
            )
    finally:
        engine.dispose()


def _run_business_command(arguments: argparse.Namespace) -> None:
    """Exécute une commande dans une transaction atomique."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            signed_contract = None
            with session.begin():
                actor = get_current_actor(session, _jwt_secret())
                set_actor_context(actor)
                signed_contract = _dispatch_business_command(
                    session,
                    actor,
                    arguments,
                )
            if signed_contract is not None:
                capture_contract_signature(actor, signed_contract)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Exécute une commande et transforme les erreurs en messages CLI."""
    load_dotenv()
    configure_monitoring()
    arguments = build_parser().parse_args(argv)

    try:
        if arguments.command == "login":
            _run_login(arguments.identifier)
        elif arguments.command == "logout":
            if logout():
                print_success("Déconnexion réussie.")
            else:
                print_info("Aucune session active.")
        elif arguments.command == "whoami":
            _run_whoami()
        elif arguments.command not in AUTHENTICATION_COMMANDS:
            _run_business_command(arguments)
    except IntegrityError:
        print_error(
            "Les données sont en conflit avec une valeur existante "
            "ou une contrainte de la base."
        )
        return 1
    except (
        AuthenticationRequiredError,
        AuthorizationError,
        ExpiredAccessTokenError,
        InvalidAccessTokenError,
        InvalidCredentialsError,
        TokenConfigurationError,
        ValueError,
    ) as error:
        print_error(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
