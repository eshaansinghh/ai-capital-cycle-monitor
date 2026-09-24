"""Tests for the filing-text reader. HTML snippets are software fixtures shaped like SEC filings."""

import pytest

from ai_capital_cycle_monitor.pipelines.filing_text import find_rows, parse_number, to_lines

PRETTY_PRINTED = """
<p>CASH FLOWS STATEMENTS</p>
<table>
  <tr>
    <td><p><span>
        Net cash from operations
    </span></p></td>
    <td><p><span>&#160;</span></p></td>
    <td><p><span>
        45,057
    </span></p></td>
    <td><p><span>$</span></p></td>
    <td><p><span>(1,234</span></p></td><td><span>)</span></td>
    <td><p><span>&#8212;</span></p></td>
  </tr>
  <tr><td>Additions to property and equipment</td><td>( 19,394</td><td>)</td></tr>
</table>
<p>Some prose with 12,345 in it.</p>
"""


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("45,057", 45057.0),
        ("(19,394)", -19394.0),
        ("(19,394", -19394.0),
        ("$ 1,200.5", 1200.5),
        ("-", 0.0),
        ("5%", None),
        ("Total", None),
        ("", None),
    ],
)
def test_parse_number(cell: str, expected: float | None) -> None:
    assert parse_number(cell) == expected


def test_source_newlines_inside_cells_do_not_split_a_row() -> None:
    lines = to_lines(PRETTY_PRINTED)
    assert any(line.startswith("Net cash from operations |") for line in lines)


def test_rows_carry_label_numbers_and_the_statement_heading() -> None:
    (row,) = find_rows(to_lines(PRETTY_PRINTED), r"^Net cash from operations")
    assert row.label == "Net cash from operations"
    assert row.numbers[0] == 45057.0
    assert -1234.0 in row.numbers
    assert row.heading == "CASH FLOWS STATEMENTS"


def test_bracketed_amounts_are_negative_and_dashes_are_zero() -> None:
    (row,) = find_rows(to_lines(PRETTY_PRINTED), r"^Additions to property")
    assert row.numbers[0] == -19394.0
    (cash,) = find_rows(to_lines(PRETTY_PRINTED), r"^Net cash")
    assert cash.numbers[-1] == 0.0


def test_labels_without_numbers_and_prose_are_not_rows() -> None:
    assert find_rows(to_lines(PRETTY_PRINTED), r"^CASH FLOWS") == []
    assert find_rows(to_lines(PRETTY_PRINTED), r"Some prose") == []


def test_limit_caps_the_rows_returned() -> None:
    table = "<table>" + "<tr><td>Item</td><td>1,000</td></tr>" * 5 + "</table>"
    assert len(find_rows(to_lines(table), "^Item", limit=2)) == 2
