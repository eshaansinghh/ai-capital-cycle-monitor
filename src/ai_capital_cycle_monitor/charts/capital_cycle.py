"""Quarterly capex, operating cash flow and base free cash flow: the project's core question."""

import textwrap
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from ai_capital_cycle_monitor.charts.theme import FONT_FAMILY, theme_for

REQUIRED_COLUMNS = [
    "fiscal_label",
    "period_end",
    "operating_cash_flow",
    "cash_capex",
    "base_fcf",
    "operating_cash_flow_basis",
    "cash_capex_basis",
    "base_fcf_basis",
]
BILLION = 1e9
NOTE_WIDTH = 120
CROWDED_QUARTERS = 16  # above this, axis labels drop the month and rotate
HEIGHT = 520
MARGIN_TOP = 112
NOTE_PADDING = 6


def source_note(source: str, retrieved: date) -> str:
    """Chart footer: 'Source: ...; author's calculations. Data retrieved 24 September 2026.'"""
    return f"Source: {source}; author's calculations. Data retrieved {retrieved:%d %B %Y}."


def _billions(series: pd.Series) -> list[float | None]:
    return [None if pd.isna(value) else float(value) / BILLION for value in series]


def _hover(label: str, values: list[float | None], bases: pd.Series) -> list[str]:
    return [
        "not available" if value is None else f"${value:,.1f}bn ({basis})"
        for value, basis in zip(values, bases.astype(object).fillna("missing"), strict=True)
    ]


def _end_label(values: list[float | None], colour: str, surface: str) -> dict[str, object] | None:
    """Direct label for the latest available point, placed in the right margin.

    Only the endpoint is labelled, so the chart is not a wall of numbers.
    """
    for value in reversed(values):
        if value is not None:
            return {
                "text": f"Base FCF<br><b>${value:,.1f}bn</b>",
                "xref": "paper",
                "x": 1,
                "xanchor": "left",
                "xshift": 8,
                "yref": "y",
                "y": value,
                "showarrow": False,
                "align": "left",
                "bgcolor": surface,
                "font": {"size": 12, "color": colour},
            }
    return None


def quarterly_cash_cycle_figure(
    quarterly: pd.DataFrame,
    *,
    company_name: str,
    note: str,
    dark: bool = False,
    hatch_derived: bool = True,
) -> go.Figure:
    """Grouped bars for operating cash flow and capex, and a line for base FCF, in USD billions.

    Everything shares one y-axis. Missing quarters stay gaps, never zero. Bars whose value was
    derived from year-to-date differences are hatched, so reported and derived are distinguishable.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in quarterly.columns]
    if missing:
        raise ValueError(f"quarterly table is missing columns: {missing}")
    if quarterly.empty:
        raise ValueError("there are no quarters to chart")

    theme = theme_for(dark)
    frame = quarterly.sort_values("period_end")
    labels = [
        f"{label}<br>{end:%b %Y}"
        for label, end in zip(frame["fiscal_label"], frame["period_end"], strict=True)
    ]
    crowded = len(frame) > CROWDED_QUARTERS
    tick_text = list(frame["fiscal_label"]) if crowded else labels
    figure = go.Figure()

    def bars(name: str, column: str, colour: str) -> tuple[list[float | None], bool]:
        values = _billions(frame[column])
        derived = (frame[f"{column}_basis"] == "derived").fillna(False).tolist()
        shapes = ["/" if (hatch_derived and flag) else "" for flag in derived]
        figure.add_bar(
            x=labels,
            y=values,
            name=name,
            marker={
                "color": colour,
                "pattern": {
                    "shape": shapes,
                    "fillmode": "overlay",
                    "fgcolor": theme.surface,
                    "size": 6,
                    "solidity": 0.35,
                },
            },
            customdata=_hover(name, values, frame[f"{column}_basis"]),
            hovertemplate=f"{name}: %{{customdata}}<extra></extra>",
        )
        return values, any(shapes)

    _, hatched_ocf = bars("Operating cash flow", "operating_cash_flow", theme.operating_cash_flow)
    _, hatched_capex = bars("Capital expenditure", "cash_capex", theme.cash_capex)

    fcf = _billions(frame["base_fcf"])
    figure.add_scatter(
        x=labels,
        y=fcf,
        name="Base free cash flow",
        mode="lines+markers",
        line={"color": theme.base_fcf, "width": 2},
        marker={"color": theme.base_fcf, "size": 8, "line": {"color": theme.surface, "width": 2}},
        connectgaps=False,
        customdata=_hover("Base free cash flow", fcf, frame["base_fcf_basis"]),
        hovertemplate="Base free cash flow: %{customdata}<extra></extra>",
    )

    subtitle = "One shared axis. Base FCF = operating cash flow - capex."
    if hatch_derived and (hatched_ocf or hatched_capex):
        subtitle += " Hatched bars are derived from year-to-date differences."
    wrapped_note = textwrap.fill(note, NOTE_WIDTH).replace("\n", "<br>")
    end_label = _end_label(fcf, theme.ink, theme.surface)
    margin_bottom = 150 if crowded else 120
    plot_height = HEIGHT - MARGIN_TOP - margin_bottom
    note_y = (
        -(margin_bottom - NOTE_PADDING) / plot_height
    )  # bottom edge of the figure, in paper units

    figure.update_layout(
        title={
            "text": f"{company_name}: quarterly capex, operating cash flow and free cash flow",
            "subtitle": {"text": subtitle, "font": {"size": 12, "color": theme.ink_secondary}},
            "x": 0,
            "xanchor": "left",
            "y": 0.985,
            "yanchor": "top",
            "font": {"size": 17, "color": theme.ink},
        },
        barmode="group",
        bargap=0.35,
        bargroupgap=0.08,
        hovermode="x unified",
        paper_bgcolor=theme.surface,
        plot_bgcolor=theme.surface,
        font={"family": FONT_FAMILY, "color": theme.ink_secondary, "size": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.03, "x": 0, "title": {"text": ""}},
        margin={"l": 60, "r": 110, "t": MARGIN_TOP, "b": margin_bottom},
        height=HEIGHT,
        annotations=[
            {
                "text": wrapped_note,
                "xref": "paper",
                "yref": "paper",
                "x": 0,
                "xshift": -52,
                "y": note_y,
                "xanchor": "left",
                "yanchor": "bottom",
                "showarrow": False,
                "align": "left",
                "font": {"size": 11, "color": theme.muted},
            },
            *([end_label] if end_label else []),
        ],
    )
    figure.update_xaxes(
        showgrid=False,
        linecolor=theme.baseline,
        tickfont={"color": theme.ink_secondary},
        tickmode="array",
        tickvals=labels,
        ticktext=tick_text,
        tickangle=-90 if crowded else 0,
    )
    figure.update_yaxes(
        title={"text": "USD billions", "font": {"color": theme.muted}},
        gridcolor=theme.grid,
        gridwidth=1,
        zerolinecolor=theme.baseline,
        zerolinewidth=1,
        tickformat=",.0f",
        tickfont={"color": theme.muted},
    )
    return figure
