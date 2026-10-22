"""Configuration et événements de supervision envoyés à Sentry."""

import os
from typing import Any

import sentry_sdk

from models import Contract, Employee

_SENSITIVE_EXTRA_KEYS = frozenset({"argv", "sys.argv", "sys_argv"})


def scrub_sentry_event(
    event: dict[str, Any],
    hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Retire les arguments CLI, susceptibles de contenir des données CRM."""
    del hint
    extra = event.get("extra")
    if isinstance(extra, dict):
        for key in list(extra):
            if str(key).lower() in _SENSITIVE_EXTRA_KEYS:
                extra.pop(key, None)

    return event


def configure_monitoring() -> bool:
    """Configure Sentry lorsque son DSN est présent dans l'environnement."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        before_send=scrub_sentry_event,
        before_send_transaction=scrub_sentry_event,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        include_local_variables=False,
        release=os.getenv("SENTRY_RELEASE") or None,
        send_default_pii=False,
        traces_sample_rate=float(
            os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")
        ),
    )
    return True


def trace_command(command: str):
    """Crée la transaction de performance d'une commande CLI."""
    return sentry_sdk.start_transaction(
        op="cli.command",
        name=f"epicevents {command}",
    )


def set_actor_context(actor: Employee) -> None:
    """Associe les erreurs suivantes au compte courant, sans donnée privée."""
    sentry_sdk.set_user({"id": str(actor.id)})
    sentry_sdk.set_tag("employee.role", actor.role.name)


def capture_login(actor: Employee) -> None:
    """Journalise une connexion réussie."""
    set_actor_context(actor)
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("audit.event", "employee.login")
        sentry_sdk.capture_message("employee.login", level="info")


def _capture_employee_event(
    actor: Employee,
    employee: Employee,
    event_name: str,
) -> None:
    """Journalise une écriture sur un collaborateur sans donnée privée."""
    set_actor_context(actor)
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("audit.event", event_name)
        scope.set_context(
            "employee",
            {
                "id": employee.id,
                "role": employee.role.name,
            },
        )
        sentry_sdk.capture_message(event_name, level="info")


def capture_employee_created(
    actor: Employee,
    employee: Employee,
) -> None:
    """Journalise la création réussie d'un collaborateur."""
    _capture_employee_event(actor, employee, "employee.created")


def capture_employee_updated(
    actor: Employee,
    employee: Employee,
) -> None:
    """Journalise la modification réussie d'un collaborateur."""
    _capture_employee_event(actor, employee, "employee.updated")


def capture_contract_signature(
    actor: Employee,
    contract: Contract,
) -> None:
    """Journalise le passage d'un contrat à l'état signé."""
    set_actor_context(actor)
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("audit.event", "contract.signed")
        scope.set_context(
            "contract",
            {
                "id": contract.id,
                "client_id": contract.client_id,
            },
        )
        sentry_sdk.capture_message("contract.signed", level="info")
