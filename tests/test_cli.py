"""Tests for CLI parsing and error handling. Nothing here touches the network."""

import pytest

from ai_capital_cycle_monitor import cli
from ai_capital_cycle_monitor.pipelines.build import BuildError


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])
    assert exit_info.value.code == 2


@pytest.mark.parametrize("command", ["verify-identity", "audit-tags", "build"])
def test_each_command_takes_a_ticker_and_refresh_flag(command: str) -> None:
    args = cli.build_parser().parse_args([command, "MSFT", "--refresh"])
    assert (args.command, args.ticker, args.refresh) == (command, "MSFT", True)


def test_expected_errors_become_a_message_and_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_args: object) -> int:
        raise BuildError("something went wrong")

    monkeypatch.setitem(cli.COMMANDS, "build", fail)
    assert cli.main(["build", "MSFT"]) == 2
    assert "error: something went wrong" in capsys.readouterr().err


def test_unexpected_errors_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def crash(_args: object) -> int:
        raise ZeroDivisionError

    monkeypatch.setitem(cli.COMMANDS, "build", crash)
    with pytest.raises(ZeroDivisionError):
        cli.main(["build", "MSFT"])
