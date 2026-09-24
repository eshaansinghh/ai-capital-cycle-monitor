"""Load and validate the YAML configuration files."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from ai_capital_cycle_monitor.schemas.config import Company, EventDefinition, MetricDefinition
from ai_capital_cycle_monitor.utils.paths import CONFIG_DIR


def _load_list(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    items = (document or {}).get(key)
    if not isinstance(items, list):
        raise ValueError(f"{path.name} must contain a top-level list under '{key}'")
    return items


def _ensure_unique(values: list[str], label: str, path: Path) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"{path.name} has duplicate {label}: {duplicates}")


def _load[T: BaseModel](
    path: Path, key: str, model: type[T], identity: Callable[[T], str], label: str
) -> list[T]:
    records = [model.model_validate(item) for item in _load_list(path, key)]
    _ensure_unique([identity(record) for record in records], label, path)
    return records


def load_companies(path: Path = CONFIG_DIR / "companies.yml") -> list[Company]:
    return _load(path, "companies", Company, lambda company: company.ticker, "tickers")


def load_metrics(path: Path = CONFIG_DIR / "metrics.yml") -> list[MetricDefinition]:
    return _load(path, "metrics", MetricDefinition, lambda metric: metric.id, "metric ids")


def load_events(path: Path = CONFIG_DIR / "events.yml") -> list[EventDefinition]:
    return _load(path, "events", EventDefinition, lambda event: event.event_id, "event ids")
