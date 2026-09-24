"""Canonical project paths, resolved relative to the repository root."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_REGISTRY_PATH = DATA_DIR / "source_registry.csv"
