"""Présentation Rich des données et messages de la CLI."""

from collections.abc import Iterable
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from models import Client, Contract, Employee, Event

console = Console()
error_console = Console(stderr=True)


def _cell(value: Any) -> Text:
    """Convertit une valeur en texte sans interpréter de balises Rich."""
    return Text("-" if value is None or value == "" else str(value))


def _display_table(
    title: str,
    columns: tuple[str, ...],
    rows: Iterable[tuple[Any, ...]],
) -> None:
    """Affiche un tableau ou un message explicite si la collection est vide."""
    materialized_rows = list(rows)
    if not materialized_rows:
        print_info("Aucun résultat.")
        return

    table = Table(title=title, header_style="bold cyan")
    for column in columns:
        table.add_column(column)
    for row in materialized_rows:
        table.add_row(*(_cell(value) for value in row))
    console.print(table)


def display_employees(employees: list[Employee]) -> None:
    """Affiche les collaborateurs et leur département."""
    _display_table(
        "Collaborateurs",
        ("ID", "Numéro", "Nom", "E-mail", "Département"),
        (
            (
                employee.id,
                employee.employee_number,
                employee.full_name,
                employee.email,
                employee.role.name,
            )
            for employee in employees
        ),
    )


def display_clients(clients: list[Client]) -> None:
    """Affiche les clients et leur commercial responsable."""
    _display_table(
        "Clients",
        (
            "ID",
            "Nom",
            "E-mail",
            "Téléphone",
            "Entreprise",
            "Commercial",
            "Dernier contact",
        ),
        (
            (
                client.id,
                client.full_name,
                client.email,
                client.phone,
                client.company_name,
                client.commercial.full_name,
                client.last_contact_at,
            )
            for client in clients
        ),
    )


def display_contracts(contracts: list[Contract]) -> None:
    """Affiche les informations principales des contrats."""
    _display_table(
        "Contrats",
        ("ID", "Client", "Total", "Restant", "Signé", "Créé le"),
        (
            (
                contract.id,
                contract.client.full_name,
                f"{contract.total_amount:.2f}",
                f"{contract.remaining_amount:.2f}",
                "oui" if contract.is_signed else "non",
                contract.created_at,
            )
            for contract in contracts
        ),
    )


def display_events(events: list[Event]) -> None:
    """Affiche les informations opérationnelles des événements."""
    _display_table(
        "Événements",
        (
            "ID",
            "Nom",
            "Contrat",
            "Début",
            "Fin",
            "Lieu",
            "Participants",
            "Support",
            "Notes",
        ),
        (
            (
                event.id,
                event.name,
                event.contract_id,
                event.start_date.isoformat(sep=" ", timespec="minutes"),
                event.end_date.isoformat(sep=" ", timespec="minutes"),
                event.location,
                event.attendees,
                event.support.full_name if event.support else "non affecté",
                event.notes,
            )
            for event in events
        ),
    )


def print_success(message: str) -> None:
    """Affiche une confirmation homogène."""
    console.print(Text.assemble(("[OK] ", "bold green"), _cell(message)))


def print_info(message: str) -> None:
    """Affiche une information neutre."""
    console.print(Text.assemble(("Info : ", "bold cyan"), _cell(message)))


def print_error(error: object) -> None:
    """Affiche une erreur sur la sortie d'erreur du terminal."""
    error_console.print(
        Text.assemble(("Erreur : ", "bold red"), _cell(error))
    )
