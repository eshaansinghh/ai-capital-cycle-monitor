"""Tests for the SEC client using a fake session. No network access is involved.

URLs and accession numbers below are format examples for URL construction only.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import requests

from ai_capital_cycle_monitor.clients.raw_store import RawStore
from ai_capital_cycle_monitor.clients.sec import (
    SecClient,
    SecRequestError,
    company_facts_url,
    filing_document_url,
    filing_index_url,
    normalise_cik,
    submissions_url,
)
from ai_capital_cycle_monitor.utils.settings import Settings

AGENT = "Unit Test unit.test@invalid.test"
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@dataclass
class FakeResponse:
    status_code: int
    content: bytes


@dataclass
class FakeSession:
    responses: list[FakeResponse | Exception]
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> FakeResponse:
        self.calls.append((url, headers))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def _client(tmp_path: Path, session: FakeSession, clock: Clock | None = None) -> SecClient:
    return SecClient(
        Settings(sec_user_agent=AGENT),
        RawStore(tmp_path),
        session=session,
        min_interval_seconds=0,
        clock=clock or Clock(),
    )


def test_cik_is_zero_padded_and_validated() -> None:
    assert normalise_cik(789019) == "0000789019"
    assert normalise_cik("0000789019") == "0000789019"
    for bad in ("abc", "0", "12345678901", ""):
        with pytest.raises(ValueError):
            normalise_cik(bad)


def test_url_builders() -> None:
    assert company_facts_url(1) == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
    assert submissions_url(1) == "https://data.sec.gov/submissions/CIK0000000001.json"
    accession = "0000000001-26-000001"
    assert filing_index_url("0000000001", accession) == (
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/0000000001-26-000001-index.htm"
    )
    assert filing_document_url(1, accession, "doc.htm").endswith("/000000000126000001/doc.htm")
    with pytest.raises(ValueError):
        filing_index_url(1, "not-an-accession")
    with pytest.raises(ValueError):
        filing_document_url(1, accession, "../doc.htm")


def test_fetch_stores_snapshot_and_sends_user_agent(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, b'{"ok": true}')])
    snapshot = _client(tmp_path, session).company_facts(1)
    assert snapshot.read_json() == {"ok": True}
    assert snapshot.url == company_facts_url(1)
    assert snapshot.retrieved_at_utc == T0
    ((url, headers),) = session.calls
    assert url == company_facts_url(1)
    assert headers["User-Agent"] == AGENT


def test_user_agent_is_never_written_to_disk_or_repr(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeSession([FakeResponse(200, b"{}")]))
    client.submissions(1)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert AGENT.encode() not in path.read_bytes()
    assert AGENT not in repr(client)


def test_fresh_snapshot_is_reused_without_a_request(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, b"{}")])
    clock = Clock()
    client = _client(tmp_path, session, clock)
    client.company_facts(1)
    clock.now = T0 + timedelta(hours=1)
    client.company_facts(1)
    assert len(session.calls) == 1


def test_stale_snapshot_and_refresh_trigger_a_new_request(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, b'{"v": 1}'), FakeResponse(200, b'{"v": 2}')])
    clock = Clock()
    client = _client(tmp_path, session, clock)
    client.company_facts(1)
    clock.now = T0 + timedelta(hours=25)
    assert client.company_facts(1).read_json() == {"v": 2}
    assert len(session.calls) == 2

    session.responses.append(FakeResponse(200, b'{"v": 3}'))
    clock.now = T0 + timedelta(hours=25, seconds=1)
    assert client.company_facts(1, refresh=True).read_json() == {"v": 3}


def test_filing_documents_are_reused_indefinitely(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, b"<html></html>")])
    clock = Clock()
    client = _client(tmp_path, session, clock)
    accession = "0000000001-26-000001"
    first = client.filing_document(1, accession, "doc.htm")
    clock.now = T0 + timedelta(days=400)
    assert client.filing_document(1, accession, "doc.htm") == first
    assert first.path.suffix == ".htm"
    assert len(session.calls) == 1


def test_http_errors_report_status_and_url_but_not_the_user_agent(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeSession([FakeResponse(403, b"denied")]))
    with pytest.raises(SecRequestError) as error:
        client.company_facts(1)
    message = str(error.value)
    assert "403" in message
    assert company_facts_url(1) in message
    assert AGENT not in message


def test_network_failures_are_wrapped_without_headers(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeSession([requests.ConnectionError("boom")]))
    with pytest.raises(SecRequestError) as error:
        client.company_facts(1)
    assert AGENT not in str(error.value)
    assert RawStore(tmp_path).latest("companyfacts", "CIK0000000001") is None


def test_older_submissions_pages_are_fetched_by_validated_name(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, b'{"form": []}')])
    name = "CIK0000000001-submissions-001.json"
    snapshot = _client(tmp_path, session).submissions_page(name)
    assert snapshot.url == f"https://data.sec.gov/submissions/{name}"
    assert snapshot.read_json() == {"form": []}
    for bad in ("../CIK0000000001-submissions-001.json", "submissions-001.json", "CIK1.json"):
        with pytest.raises(ValueError, match="submissions page name"):
            _client(tmp_path, FakeSession([])).submissions_page(bad)
