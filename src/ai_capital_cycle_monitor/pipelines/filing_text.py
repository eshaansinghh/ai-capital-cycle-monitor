"""Read printed statement rows from a stored filing, for manual reconciliation.

This is deliberately independent of the XBRL facts: it works on the visible table text of the
filing's HTML, so a value read here is a check on the pipeline and not another view of the same
data. It is a reading aid. A person still confirms each row against the filing.
"""

import html
import re
from dataclasses import dataclass

_AMOUNT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
_DASHES = {chr(0x2014), chr(0x2013), "-"}  # em dash, en dash, hyphen
_HEADING = re.compile(r"(statements?|balancesheets?)", re.IGNORECASE)
_INVISIBLE = {chr(0xA0): " ", chr(0x200B): "", chr(0x202F): " ", chr(0x2009): " "}


@dataclass(frozen=True)
class FilingRow:
    """One table row: its label, the numbers printed on it (negative if bracketed) and context."""

    line: int
    label: str
    numbers: tuple[float, ...]
    raw: str
    heading: str


def _table_to_text(match: re.Match[str]) -> str:
    """Inside a table only row ends start a new line. Filings often wrap each cell in paragraphs."""
    block = re.sub(r"(?i)</t[dh]\s*>", " | ", match.group(0))
    block = re.sub(r"(?i)</tr\s*>", "\x01", block)
    block = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block))  # source newlines are not rows
    return "\n" + block.replace("\x01", "\n") + "\n"


def to_lines(document: str) -> list[str]:
    """Turn filing HTML into one text line per table row, with cells separated by ' | '."""
    body = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", document)
    body = re.sub(r"(?is)<table.*?</table>", _table_to_text, body)
    body = re.sub(r"(?i)<br\s*/?>|</p\s*>|</h[1-6]\s*>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    for character, replacement in _INVISIBLE.items():
        text = text.replace(character, replacement)
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw)
        line = re.sub(r"(\|\s*)+", "| ", line).strip(" |")
        if line:
            lines.append(line)
    return lines


def parse_number(cell: str) -> float | None:
    """Parse a printed amount: '(1,234)' is negative, a dash is zero, anything else is None."""
    text = cell.strip().replace("$", "").replace(" ", "")
    if text in _DASHES:
        return 0.0
    match = _AMOUNT.fullmatch(text.strip("()"))
    if not match:
        return None
    value = float(match.group(1).replace(",", "") + (match.group(2) or ""))
    return -value if text.startswith("(") else value


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")]


def find_rows(
    lines: list[str], label: re.Pattern[str] | str, *, limit: int = 12
) -> list[FilingRow]:
    """Rows whose first cell matches `label` and that carry at least one number."""
    matcher = re.compile(label, re.IGNORECASE) if isinstance(label, str) else label
    rows: list[FilingRow] = []
    for index, line in enumerate(lines):
        cells = _cells(line)
        if not cells or not matcher.search(cells[0]):
            continue
        numbers = tuple(value for cell in cells[1:] if (value := parse_number(cell)) is not None)
        if not numbers:
            continue
        rows.append(FilingRow(index + 1, cells[0], numbers, line, _nearest_heading(lines, index)))
        if len(rows) == limit:
            break
    return rows


def _nearest_heading(lines: list[str], index: int, lookback: int = 260) -> str:
    for back in range(index, max(index - lookback, -1), -1):
        candidate = _cells(lines[back])[0]
        if len(candidate) < 70 and _HEADING.search(candidate.replace(" ", "")):
            return candidate
    return ""


def find_text(
    lines: list[str], pattern: re.Pattern[str] | str, *, limit: int = 8, width: int = 260
) -> list[tuple[int, str]]:
    """Prose lines matching `pattern` anywhere (not only table labels), trimmed around the match."""
    matcher = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = matcher.search(line)
        if not match:
            continue
        room = max(width - len(match.group()), 0)
        start = max(match.start() - room // 2, 0)
        found.append((index + 1, line[start : start + max(width, len(match.group()))]))
        if len(found) == limit:
            break
    return found
