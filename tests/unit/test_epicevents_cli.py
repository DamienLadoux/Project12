"""Tests unitaires des commandes d'authentification de la CLI."""

from unittest.mock import patch

import pytest

from epicevents import main


@patch("epicevents.logout", return_value=True)
def test_logout_command_reports_success(mock_logout, capsys):
    """La commande logout confirme la suppression de la session."""
    exit_code = main(["logout"])

    assert exit_code == 0
    assert "Déconnexion réussie" in capsys.readouterr().out
    mock_logout.assert_called_once_with()


@patch("epicevents.logout", return_value=False)
def test_logout_without_session_is_not_an_error(mock_logout, capsys):
    """La déconnexion reste idempotente en l'absence de jeton."""
    exit_code = main(["logout"])

    assert exit_code == 0
    assert "Aucune session active" in capsys.readouterr().out


@patch("epicevents._run_whoami", side_effect=PermissionError("session invalide"))
def test_unexpected_permission_error_is_not_silenced(mock_whoami):
    """Une exception non métier continue à signaler un défaut du programme."""
    with pytest.raises(PermissionError):
        main(["whoami"])
