"""Tests for settings loading. Values are synthetic and exist only in pytest temp directories."""

import os
from pathlib import Path

import pytest

from ai_capital_cycle_monitor.utils.paths import PROJECT_ROOT
from ai_capital_cycle_monitor.utils.settings import (
    USER_AGENT_VARIABLE,
    SettingsError,
    load_settings,
)

SYNTHETIC_AGENT = "Unit Test unit.test@invalid.test"


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(USER_AGENT_VARIABLE, raising=False)


def _env_file(tmp_path: Path, content: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    return path


def test_reads_user_agent_from_env_file(tmp_path: Path) -> None:
    path = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="{SYNTHETIC_AGENT}"\n')
    assert load_settings(path).sec_user_agent == SYNTHETIC_AGENT


def test_environment_variable_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="Other Person other@invalid.test"\n')
    monkeypatch.setenv(USER_AGENT_VARIABLE, SYNTHETIC_AGENT)
    assert load_settings(path).sec_user_agent == SYNTHETIC_AGENT


def test_loading_does_not_modify_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="{SYNTHETIC_AGENT}"\n')
    load_settings(path)
    assert USER_AGENT_VARIABLE not in os.environ


def test_missing_file_and_variable_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="not set"):
        load_settings(tmp_path / "absent.env")


def test_committed_template_placeholder_is_rejected() -> None:
    with pytest.raises(SettingsError, match="placeholder"):
        load_settings(PROJECT_ROOT / ".env.example")


def test_user_agent_without_email_is_rejected(tmp_path: Path) -> None:
    path = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="Unit Test"\n')
    with pytest.raises(SettingsError, match="contact email"):
        load_settings(path)


def test_repr_and_errors_never_reveal_the_value(tmp_path: Path) -> None:
    path = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="{SYNTHETIC_AGENT}"\n')
    settings = load_settings(path)
    assert SYNTHETIC_AGENT not in repr(settings)
    assert SYNTHETIC_AGENT not in str(settings)

    bad = _env_file(tmp_path, f'{USER_AGENT_VARIABLE}="Unit Test unit.test@example.com"\n')
    with pytest.raises(SettingsError) as error:
        load_settings(bad)
    assert "unit.test" not in str(error.value)
