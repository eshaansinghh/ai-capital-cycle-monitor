"""Headless UI tests for the Streamlit app using AppTest.

Populated-state tests point the page at a temporary directory holding a structure-only synthetic
dataset. It never touches the project's data directory and is never shown to users.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ai_capital_cycle_monitor.pipelines.datasets import write_dataset
from ai_capital_cycle_monitor.pipelines.financials import build_company_dataset
from ai_capital_cycle_monitor.schemas.provenance import SourceRecord
from ai_capital_cycle_monitor.utils import paths
from ai_capital_cycle_monitor.utils.registry import upsert_source_records
from ai_capital_cycle_monitor.views import capital_cycle as view_module
from synthetic import COMPANY, MAPPINGS, SNAPSHOT, payload

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
CAPITAL_CYCLE_PAGE = "app_pages/capital_cycle.py"


def _open(monkeypatch: pytest.MonkeyPatch, data_dir: Path, ticker: str = "TEST") -> AppTest:
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(view_module, "DEFAULT_TICKER", ticker)
    monkeypatch.setattr(view_module, "find_company", lambda _ticker, _companies=None: COMPANY)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.switch_page(CAPITAL_CYCLE_PAGE).run()
    return app


@pytest.fixture
def built(tmp_path: Path) -> Path:
    (tmp_path / "source_registry.csv").write_text(
        ",".join(SourceRecord.model_fields) + "\n", encoding="utf-8"
    )
    dataset = build_company_dataset(COMPANY, MAPPINGS, payload(), SNAPSHOT)
    write_dataset(dataset, tmp_path)
    upsert_source_records(dataset.registry_records, tmp_path / "source_registry.csv")
    return tmp_path


def test_overview_page_renders_and_states_the_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "AI Capital Cycle Monitor"
    assert "Phase 2" in app.info[0].value
    assert "not investment advice" in app.caption[-1].value


def test_empty_state_explains_how_to_build_and_shows_no_chart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _open(monkeypatch, tmp_path, ticker="MSFT")
    assert not app.exception
    assert "has not been built" in app.info[0].value
    assert app.code[0].value == "uv run ai-capital-cycle build MSFT"
    assert not app.get("plotly_chart")
    assert not app.metric


def test_populated_page_shows_metrics_chart_and_source_note(
    monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    app = _open(monkeypatch, built)
    assert not app.exception
    assert [m.label.split(" (")[0] for m in app.metric[:3]] == [
        "Capital expenditure",
        "Operating cash flow",
        "Base free cash flow",
    ]
    assert len(app.get("plotly_chart")) == 1
    assert any("Data retrieved 02 January 2026" in c.value for c in app.caption)
    assert any("Educational research" in c.value for c in app.caption)
    assert len(app.status) == 3  # AppTest exposes expanders as status blocks


def test_changing_filters_reruns_without_error(
    monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    app = _open(monkeypatch, built)
    app.toggle(key="capital_cycle_hatch").set_value(False).run()
    assert not app.exception
    app.button_group(key="capital_cycle_window").set_value("Last 8").run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1


def test_untraceable_series_withhold_the_chart(
    monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    registry = built / "source_registry.csv"
    registry.write_text(",".join(SourceRecord.model_fields) + "\n", encoding="utf-8")
    app = _open(monkeypatch, built)
    assert not app.exception
    assert "Chart withheld" in app.error[0].value
    assert not app.get("plotly_chart")
