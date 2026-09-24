"""Thin SEC EDGAR client: polite to the SEC, cached through the raw store, provenance preserved."""

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ai_capital_cycle_monitor.clients.raw_store import RawStore, Snapshot
from ai_capital_cycle_monitor.utils.settings import Settings

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_MAX_AGE = timedelta(hours=24)

_DATA_HOST = "https://data.sec.gov"
_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_DOCUMENT_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class SecRequestError(RuntimeError):
    """A request to the SEC failed. Messages carry the URL and status, never request headers."""


def normalise_cik(cik: str | int) -> str:
    """Return the ten-digit, zero-padded CIK used by SEC APIs."""
    text = str(cik).strip()
    if not text.isdigit() or int(text) == 0 or len(text) > 10:
        raise ValueError(f"not a valid CIK: {cik!r}")
    return text.zfill(10)


def company_facts_url(cik: str | int) -> str:
    return f"{_DATA_HOST}/api/xbrl/companyfacts/CIK{normalise_cik(cik)}.json"


def submissions_url(cik: str | int) -> str:
    return f"{_DATA_HOST}/submissions/CIK{normalise_cik(cik)}.json"


def _accession_folder(accession: str) -> str:
    if not _ACCESSION.match(accession):
        raise ValueError(f"not a valid accession number: {accession!r}")
    return accession.replace("-", "")


def filing_index_url(cik: str | int, accession: str) -> str:
    """Filing index page. Constructible for any accession, unlike the primary-document URL."""
    folder = _accession_folder(accession)
    return f"{_ARCHIVES}/{int(normalise_cik(cik))}/{folder}/{accession}-index.htm"


def filing_document_url(cik: str | int, accession: str, primary_document: str) -> str:
    if not _DOCUMENT_NAME.match(primary_document):
        raise ValueError(f"not a valid document name: {primary_document!r}")
    folder = _accession_folder(accession)
    return f"{_ARCHIVES}/{int(normalise_cik(cik))}/{folder}/{primary_document}"


class _Session(Protocol):
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> Any: ...


def _default_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


class SecClient:
    """Fetches SEC responses into the raw store, reusing a snapshot younger than `max_age`."""

    def __init__(
        self,
        settings: Settings,
        store: RawStore,
        *,
        session: _Session | None = None,
        min_interval_seconds: float = 0.25,
        timeout_seconds: float = 30.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._user_agent = settings.sec_user_agent
        self._store = store
        self._session: _Session = session or _default_session()
        self._min_interval = min_interval_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._last_request: float | None = None

    def __repr__(self) -> str:
        return f"SecClient(store={self._store.root})"

    def company_tickers(
        self, *, max_age: timedelta | None = DEFAULT_MAX_AGE, refresh: bool = False
    ) -> Snapshot:
        return self._fetch(
            "company_tickers", "all", COMPANY_TICKERS_URL, max_age=max_age, refresh=refresh
        )

    def submissions(
        self, cik: str | int, *, max_age: timedelta | None = DEFAULT_MAX_AGE, refresh: bool = False
    ) -> Snapshot:
        cik10 = normalise_cik(cik)
        return self._fetch(
            "submissions", f"CIK{cik10}", submissions_url(cik10), max_age=max_age, refresh=refresh
        )

    def company_facts(
        self, cik: str | int, *, max_age: timedelta | None = DEFAULT_MAX_AGE, refresh: bool = False
    ) -> Snapshot:
        cik10 = normalise_cik(cik)
        return self._fetch(
            "companyfacts",
            f"CIK{cik10}",
            company_facts_url(cik10),
            max_age=max_age,
            refresh=refresh,
        )

    def filing_document(
        self, cik: str | int, accession: str, primary_document: str, *, refresh: bool = False
    ) -> Snapshot:
        """A filed document never changes, so a stored copy is reused indefinitely."""
        cik10 = normalise_cik(cik)
        url = filing_document_url(cik10, accession, primary_document)
        return self._fetch(
            "filings",
            f"{cik10}_{_accession_folder(accession)}",
            url,
            max_age=None,
            refresh=refresh,
            suffix=Path(primary_document).suffix or ".html",
        )

    def _fetch(
        self,
        kind: str,
        key: str,
        url: str,
        *,
        max_age: timedelta | None,
        refresh: bool,
        suffix: str = ".json",
    ) -> Snapshot:
        if not refresh:
            cached = self._store.latest(kind, key)
            if cached is not None and (
                max_age is None or self._clock() - cached.retrieved_at_utc <= max_age
            ):
                return cached
        self._throttle()
        headers = {"User-Agent": self._user_agent, "Accept-Encoding": "gzip, deflate"}
        try:
            response = self._session.get(url, headers=headers, timeout=self._timeout)
        except requests.RequestException as error:
            raise SecRequestError(f"SEC request failed for {url}: {type(error).__name__}") from None
        if response.status_code != 200:
            raise SecRequestError(f"SEC request failed with HTTP {response.status_code} for {url}")
        return self._store.save(
            kind,
            key,
            body=response.content,
            url=url,
            retrieved_at=self._clock(),
            http_status=response.status_code,
            suffix=suffix,
        )

    def _throttle(self) -> None:
        """Stay well under the SEC's ten-requests-per-second limit."""
        if self._last_request is not None:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()
