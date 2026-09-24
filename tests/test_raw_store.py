"""Tests for the raw-response store. Bodies are synthetic bytes used only in temp directories."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ai_capital_cycle_monitor.clients.raw_store import RawStore, RawStoreError

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _save(store: RawStore, body: bytes, when: datetime = T0):
    return store.save(
        "kind", "key", body=body, url="https://example.com/x", retrieved_at=when, http_status=200
    )


def test_save_and_latest_round_trip(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    saved = _save(store, b'{"a": 1}')
    loaded = store.latest("kind", "key")
    assert loaded == saved
    assert loaded.read_json() == {"a": 1}
    assert loaded.url == "https://example.com/x"
    assert loaded.retrieved_at_utc == T0
    assert loaded.size_bytes == len(b'{"a": 1}')


def test_latest_is_none_when_nothing_stored(tmp_path: Path) -> None:
    assert RawStore(tmp_path).latest("kind", "key") is None


def test_latest_returns_the_newest_snapshot(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    _save(store, b"older")
    _save(store, b"newer", T0 + timedelta(hours=1))
    assert store.latest("kind", "key").read_bytes() == b"newer"


def test_snapshots_are_never_overwritten(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    first = _save(store, b"same")
    again = _save(store, b"same")
    assert again == first
    bodies = [p for p in (tmp_path / "kind" / "key").iterdir() if not p.name.endswith(".meta.json")]
    assert len(bodies) == 1


def test_tampered_body_is_detected(tmp_path: Path) -> None:
    snapshot = _save(RawStore(tmp_path), b"original")
    snapshot.path.write_bytes(b"edited")
    with pytest.raises(RawStoreError, match="checksum"):
        snapshot.read_bytes()


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", "..", "with space"])
def test_unsafe_names_are_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(RawStoreError, match="unsafe"):
        RawStore(tmp_path).latest(bad, "key")
