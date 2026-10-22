"""Test unitaire de la présentation Rich de la CLI."""

from io import StringIO

from rich.console import Console

from cli import presentation
from models import Employee, Role


def test_employees_are_displayed_in_a_readable_table(monkeypatch):
    """Le tableau expose les informations utiles d'un collaborateur."""
    output = StringIO()
    monkeypatch.setattr(
        presentation,
        "console",
        Console(file=output, color_system=None, width=120),
    )
    employee = Employee(
        id=7,
        employee_number="EMP-007",
        full_name="Alice Martin",
        email="alice@example.test",
        password_hash="hachage-de-test",
        role=Role(name="SUPPORT"),
    )

    presentation.display_employees([employee])

    rendered_table = output.getvalue()
    assert "Collaborateurs" in rendered_table
    assert "EMP-007" in rendered_table
    assert "Alice Martin" in rendered_table
    assert "SUPPORT" in rendered_table


def test_messages_use_standard_and_error_outputs(monkeypatch):
    """Les confirmations et erreurs utilisent des flux distincts."""
    standard_output = StringIO()
    error_output = StringIO()
    monkeypatch.setattr(
        presentation,
        "console",
        Console(file=standard_output, color_system=None),
    )
    monkeypatch.setattr(
        presentation,
        "error_console",
        Console(file=error_output, color_system=None),
    )

    presentation.print_success("Modification enregistrée.")
    presentation.print_error("Action interdite.")

    assert "[OK] Modification enregistrée." in standard_output.getvalue()
    assert "Erreur : Action interdite." in error_output.getvalue()
