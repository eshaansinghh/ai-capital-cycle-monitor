"""Immutable, checksummed store for raw source responses (lives under data/raw)."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_META_SUFFIX = ".meta.json"


class RawStoreError(RuntimeError):
    """A stored response is missing, corrupt or was asked for with an unsafe name."""


@dataclass(frozen=True)
class Snapshot:
    """One stored response: the body file plus the facts recorded when it was retrieved."""

    path: Path
    url: str
    retrieved_at_utc: datetime
    http_status: int
    sha256: str
    size_bytes: int

    def read_bytes(self) -> bytes:
        """Return the body, failing loudly if it no longer matches its recorded checksum."""
        body = self.path.read_bytes()
        if hashlib.sha256(body).hexdigest() != self.sha256:
            raise RawStoreError(f"{self.path.name} no longer matches its recorded checksum")
        return body

    def read_json(self) -> Any:
        return json.loads(self.read_bytes())


class RawStore:
    """Append-only: snapshots are added, never edited or overwritten."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _directory(self, kind: str, key: str) -> Path:
        for part in (kind, key):
            if not _SAFE_NAME.match(part) or part in {".", ".."}:
                raise RawStoreError(f"unsafe raw-store name: {part!r}")
        return self.root / kind / key

    def save(
        self,
        kind: str,
        key: str,
        *,
        body: bytes,
        url: str,
        retrieved_at: datetime,
        http_status: int,
        suffix: str = ".json",
    ) -> Snapshot:
        directory = self._directory(kind, key)
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(body).hexdigest()
        stamp = retrieved_at.astimezone(UTC).strftime(_STAMP_FORMAT)
        path = directory / f"{stamp}__{digest[:8]}{suffix}"
        meta_path = directory / f"{path.name}{_META_SUFFIX}"
        try:
            with path.open("xb") as handle:
                handle.write(body)
        except FileExistsError:
            return self._load(meta_path)
        meta = {
            "url": url,
            "retrieved_at_utc": retrieved_at.astimezone(UTC).isoformat(),
            "http_status": http_status,
            "sha256": digest,
            "size_bytes": len(body),
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return self._load(meta_path)

    def latest(self, kind: str, key: str) -> Snapshot | None:
        directory = self._directory(kind, key)
        if not directory.is_dir():
            return None
        metas = sorted(directory.glob(f"*{_META_SUFFIX}"))
        return self._load(metas[-1]) if metas else None

    @staticmethod
    def _load(meta_path: Path) -> Snapshot:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body_path = meta_path.with_name(meta_path.name.removesuffix(_META_SUFFIX))
        if not body_path.is_file():
            raise RawStoreError(f"{meta_path.name} has no matching body file")
        return Snapshot(
            path=body_path,
            url=meta["url"],
            retrieved_at_utc=datetime.fromisoformat(meta["retrieved_at_utc"]),
            http_status=meta["http_status"],
            sha256=meta["sha256"],
            size_bytes=meta["size_bytes"],
        )
