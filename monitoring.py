"""Configuration et événements de supervision envoyés à Sentry."""

import os

import sentry_sdk

from models import Contract, Employee


def configure_monitoring() -> bool:
    """Configure Sentry lorsque son DSN est présent dans l'environnement."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        include_local_variables=False,
        send_default_pii=False,
    )
    return True


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
