"""Load and validate the source registry (data/source_registry.csv)."""

import csv
from pathlib import Path

from pydantic import ValidationError

from ai_capital_cycle_monitor.schemas.provenance import SourceRecord
from ai_capital_cycle_monitor.utils.paths import SOURCE_REGISTRY_PATH


def load_source_registry(path: Path = SOURCE_REGISTRY_PATH) -> list[SourceRecord]:
    """Read the registry, requiring the exact schema header and validating every row.

    Blank cells become None: missing stays missing and is never coerced to zero or a default.
    """
    expected = list(SourceRecord.model_fields)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected:
            raise ValueError(f"{path.name} header must be {expected}, found {reader.fieldnames}")
        records: list[SourceRecord] = []
        for row_number, row in enumerate(reader, start=2):
            cleaned = {key: (value or None) for key, value in row.items()}
            try:
                records.append(SourceRecord.model_validate(cleaned))
            except ValidationError as error:
                raise ValueError(f"{path.name} row {row_number} is invalid:\n{error}") from error
    return records
