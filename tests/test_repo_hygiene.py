"""Guard rails: secrets and data contents must never be committed."""

import re
import subprocess

import pytest

from ai_capital_cycle_monitor.utils.paths import PROJECT_ROOT

DATA_STAGES = ("raw", "interim", "processed")


def test_env_template_contains_placeholders_only() -> None:
    text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    emails = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    assert emails, "template should show the expected User-Agent format"
    assert all(email.endswith("@example.com") for email in emails)
    assert "your_fred_api_key_here" in text


def test_gitignore_excludes_secrets_and_data_contents() -> None:
    lines = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lines
    assert "!.env.example" in lines
    for stage in DATA_STAGES:
        assert f"data/{stage}/*" in lines
        assert f"!data/{stage}/.gitkeep" in lines


def test_git_tracks_no_secrets_or_data_contents() -> None:
    result = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        pytest.skip("not inside a Git checkout")
    tracked = result.stdout.splitlines()
    assert ".env" not in tracked
    for path in tracked:
        for stage in DATA_STAGES:
            if path.startswith(f"data/{stage}/"):
                assert path == f"data/{stage}/.gitkeep", path
