"""Tests for the capex / operating cash flow / base FCF chart.

The table comes from the structure-only synthetic fixture, so these check chart construction
(traces, units, gaps, hatching, notes, palette), not any company's numbers.
"""

from datetime import date

import pandas as pd
import pytest

from ai_capital_cycle_monitor.charts.capital_cycle import (
    quarterly_cash_cycle_figure,
    source_note,
)
from ai_capital_cycle_monitor.charts.theme import DARK, LIGHT
from ai_capital_cycle_monitor.pipelines.financials import build_company_dataset
from synthetic import COMPANY, MAPPINGS, SNAPSHOT, payload

NOTE = source_note("Test source (2026)", date(2026, 9, 24))


def _quarterly(capex: list[int | None] | None = None) -> pd.DataFrame:
    return build_company_dataset(COMPANY, MAPPINGS, payload(capex=capex), SNAPSHOT).quarterly


def _figure(quarterly: pd.DataFrame | None = None, **kwargs: object):
    return quarterly_cash_cycle_figure(
        _quarterly() if quarterly is None else quarterly,
        company_name="Test Co",
        note=NOTE,
        **kwargs,
    )


def test_source_note_names_source_and_retrieval_date() -> None:
    assert (
        NOTE
        == "Source: Test source (2026); author's calculations. Data retrieved 24 September 2026."
    )


def test_three_series_share_one_axis_in_usd_billions() -> None:
    figure = _figure()
    assert [trace.name for trace in figure.data] == [
        "Operating cash flow",
        "Capital expenditure",
        "Base free cash flow",
    ]
    ocf, capex, fcf = (list(trace.y) for trace in figure.data)
    assert ocf == [40 / 1e9, 50 / 1e9, 60 / 1e9, 70 / 1e9]
    assert fcf == [pytest.approx(o - c) for o, c in zip(ocf, capex, strict=True)]
    assert "yaxis2" not in figure.layout.to_plotly_json()
    assert figure.layout.yaxis.title.text == "USD billions"


def test_missing_values_are_gaps_not_zero() -> None:
    figure = _figure(_quarterly(capex=[10, 25, None, 70]))
    capex, fcf = list(figure.data[1].y), list(figure.data[2].y)
    assert capex[2:] == [None, None]
    assert fcf[2:] == [None, None]
    assert figure.data[2].connectgaps is False
    assert "not available" in figure.data[1].customdata[2]


def test_derived_bars_are_hatched_and_reported_bars_are_solid() -> None:
    figure = _figure()
    assert list(figure.data[0].marker.pattern.shape) == ["", "/", "/", "/"]
    assert "Hatched bars are derived" in figure.layout.title.subtitle.text


def test_hatching_can_be_turned_off_and_the_hatch_note_disappears() -> None:
    figure = _figure(hatch_derived=False)
    assert set(figure.data[0].marker.pattern.shape) == {""}
    assert "Hatched" not in figure.layout.title.subtitle.text


def _end_labels(figure) -> list:
    return [a for a in figure.layout.annotations if a.text.startswith("Base FCF")]


def test_only_the_latest_available_point_is_directly_labelled() -> None:
    (label,) = _end_labels(_figure())
    assert "$0.0bn" in label.text
    assert label.y == pytest.approx(45 / 1e9)
    (gap_label,) = _end_labels(_figure(_quarterly(capex=[10, 25, None, 70])))
    assert gap_label.y == pytest.approx(35 / 1e9)  # last quarter with a value, not a zero


def test_no_end_label_when_base_fcf_is_entirely_missing() -> None:
    quarterly = _quarterly()
    quarterly["base_fcf"] = pd.array([None] * len(quarterly), dtype="Int64")
    assert _end_labels(_figure(quarterly)) == []


def test_source_note_and_as_of_date_are_on_the_chart() -> None:
    annotation = _figure().layout.annotations[0]
    assert "Source: Test source (2026)" in annotation.text
    assert "Data retrieved 24 September 2026" in annotation.text


def test_x_labels_carry_fiscal_label_and_calendar_month() -> None:
    assert next(iter(_figure().data[0].x)) == "FY25 Q1<br>Sep 2024"


def test_theme_follows_the_requested_mode() -> None:
    light, dark = _figure(), _figure(dark=True)
    assert light.data[0].marker.color == LIGHT.operating_cash_flow
    assert dark.data[0].marker.color == DARK.operating_cash_flow
    assert light.layout.paper_bgcolor == LIGHT.surface
    assert dark.layout.paper_bgcolor == DARK.surface


def test_validated_palette_is_pinned() -> None:
    assert (LIGHT.operating_cash_flow, LIGHT.cash_capex) == ("#2a78d6", "#0f9d94")
    assert (DARK.operating_cash_flow, DARK.cash_capex) == ("#3987e5", "#17a89d")


def test_empty_or_incomplete_tables_are_rejected() -> None:
    with pytest.raises(ValueError, match="no quarters"):
        _figure(_quarterly().iloc[0:0])
    with pytest.raises(ValueError, match="missing columns"):
        _figure(_quarterly().drop(columns=["base_fcf"]))


def _many_quarters(count: int = 20) -> pd.DataFrame:
    frame = _quarterly()
    rows = []
    for index in range(count):
        row = frame.iloc[index % len(frame)].copy()
        row["period_end"] = pd.Timestamp("2015-03-31") + pd.DateOffset(months=3 * index)
        row["fiscal_label"] = f"FY{15 + index // 4:02d} Q{index % 4 + 1}"
        rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def test_many_quarters_use_short_rotated_ticks_but_keep_the_month_in_the_hover() -> None:
    figure = _figure(_many_quarters(20))
    assert figure.layout.xaxis.tickangle == -90
    assert list(figure.layout.xaxis.ticktext)[:2] == ["FY15 Q1", "FY15 Q2"]
    assert "<br>" in next(iter(figure.layout.xaxis.tickvals))  # full label stays the category
    assert figure.layout.margin.b == 150


def test_few_quarters_keep_two_line_horizontal_ticks() -> None:
    figure = _figure()
    assert figure.layout.xaxis.tickangle == 0
    assert "<br>" in next(iter(figure.layout.xaxis.ticktext))


def test_source_note_sits_at_the_figure_bottom_so_ticks_cannot_cover_it() -> None:
    for quarterly in (_quarterly(), _many_quarters(30)):
        figure = _figure(quarterly)
        note = figure.layout.annotations[0]
        margin = figure.layout.margin
        plot_height = figure.layout.height - margin.t - margin.b
        assert note.yanchor == "bottom"
        # Its bottom edge sits a few pixels above the bottom of the figure, below the tick labels.
        assert note.y == pytest.approx(-(margin.b - 6) / plot_height)
        assert note.y < 0
