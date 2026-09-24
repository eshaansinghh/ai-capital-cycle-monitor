"""Runtime settings from the environment and the local, gitignored .env file."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from ai_capital_cycle_monitor.utils.paths import PROJECT_ROOT

USER_AGENT_VARIABLE = "SEC_EDGAR_USER_AGENT"
_PLACEHOLDER_MARKERS = ("example.com", "your name", "your_")
_CONTACT_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


class SettingsError(RuntimeError):
    """Local configuration is missing or still a placeholder. Messages never include values."""


@dataclass(frozen=True)
class Settings:
    """Secrets are excluded from repr so they cannot leak into logs or tracebacks."""

    sec_user_agent: str = field(repr=False)


def load_settings(env_path: Path | None = None) -> Settings:
    """Read settings, with real environment variables taking precedence over the .env file.

    The process environment is not modified.
    """
    values = dotenv_values(env_path or PROJECT_ROOT / ".env")
    user_agent = (
        os.environ.get(USER_AGENT_VARIABLE) or values.get(USER_AGENT_VARIABLE) or ""
    ).strip()
    if not user_agent:
        raise SettingsError(
            f"{USER_AGENT_VARIABLE} is not set. Copy .env.example to .env and enter your real "
            "name and contact email, as required by the SEC fair-access policy."
        )
    lowered = user_agent.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        raise SettingsError(f"{USER_AGENT_VARIABLE} is still the placeholder from .env.example.")
    if not _CONTACT_EMAIL.search(user_agent):
        raise SettingsError(f"{USER_AGENT_VARIABLE} must include a contact email address.")
    return Settings(sec_user_agent=user_agent)
