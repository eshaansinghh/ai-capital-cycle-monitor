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


def test_reading_and_listing_filings_have_their_own_arguments() -> None:
    parser = cli.build_parser()
    read = parser.parse_args(
        [
            "read-filing",
            "MSFT",
            "0001193125-26-323660",
            "msft.htm",
            "--label",
            "^Total",
            "--label",
            "x",
        ]
    )
    assert (read.ticker, read.document, read.label, read.limit) == (
        "MSFT",
        "msft.htm",
        ["^Total", "x"],
        6,
    )
    listing = parser.parse_args(["list-filings", "MSFT", "--form", "10-K", "--limit", "3"])
    assert (listing.form, listing.limit) == ("10-K", 3)


def test_reading_a_filing_needs_a_selector_and_says_so_before_touching_the_network(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["read-filing", "MSFT", "0001193125-26-323660", "msft.htm"]) == 2
    assert "at least one --label, --text or --lines" in capsys.readouterr().err
