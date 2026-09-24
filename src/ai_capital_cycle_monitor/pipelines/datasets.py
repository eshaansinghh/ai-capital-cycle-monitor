"""Read and write a company dataset as Parquet under data/interim and data/processed."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ai_capital_cycle_monitor.pipelines.financials import CompanyDataset


@dataclass(frozen=True)
class DatasetPaths:
    long: Path
    quarterly: Path
    checks: Path


def dataset_paths(data_dir: Path, ticker: str) -> DatasetPaths:
    name = ticker.lower()
    return DatasetPaths(
        long=data_dir / "interim" / f"{name}_quarterly_facts.parquet",
        quarterly=data_dir / "processed" / f"{name}_quarterly.parquet",
        checks=data_dir / "processed" / f"{name}_checks.parquet",
    )


def write_dataset(dataset: CompanyDataset, data_dir: Path) -> DatasetPaths:
    paths = dataset_paths(data_dir, dataset.ticker)
    for frame, path in (
        (dataset.long, paths.long),
        (dataset.quarterly, paths.quarterly),
        (dataset.checks, paths.checks),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
    return paths


def read_quarterly(data_dir: Path, ticker: str) -> pd.DataFrame | None:
    """The processed quarterly table, or None if the dataset has not been built."""
    path = dataset_paths(data_dir, ticker).quarterly
    return pd.read_parquet(path) if path.is_file() else None


def read_checks(data_dir: Path, ticker: str) -> pd.DataFrame | None:
    path = dataset_paths(data_dir, ticker).checks
    return pd.read_parquet(path) if path.is_file() else None


def read_long(data_dir: Path, ticker: str) -> pd.DataFrame | None:
    path = dataset_paths(data_dir, ticker).long
    return pd.read_parquet(path) if path.is_file() else None
