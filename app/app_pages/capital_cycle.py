from pathlib import Path

import streamlit as st

from ai_capital_cycle_monitor.charts.capital_cycle import quarterly_cash_cycle_figure
from ai_capital_cycle_monitor.pipelines.datasets import dataset_paths
from ai_capital_cycle_monitor.utils import paths
from ai_capital_cycle_monitor.views import capital_cycle as data

QUARTER_WINDOWS = {"Last 8": 8, "Last 12": 12, "Last 20": 20, "All": None}


@st.cache_data(show_spinner=False, max_entries=8, ttl=3600)
def load_view(data_dir: str, ticker: str, built_at: float):
    return data.load_capital_cycle_view(Path(data_dir), ticker)


def built_at(data_dir: Path, ticker: str) -> float:
    path = dataset_paths(data_dir, ticker).quarterly
    return path.stat().st_mtime if path.is_file() else 0.0


ticker = data.DEFAULT_TICKER
data_dir = paths.DATA_DIR

st.title("Capital cycle: Microsoft")
st.caption(
    "Phase 2 vertical slice. Quarterly capex, operating cash flow and standardised free cash "
    "flow from SEC filings. Does spending outrun the cash the business generates?"
)

try:
    view = load_view(str(data_dir), ticker, built_at(data_dir, ticker))
except data.TraceabilityError as error:
    st.error(f"Chart withheld: {error}", icon=":material/link_off:")
    st.stop()

if view is None:
    st.info(
        "The Microsoft dataset has not been built yet, so there is nothing to chart. "
        "Add your SEC User-Agent to `.env`, then run:",
        icon=":material/database:",
    )
    st.code(f"uv run ai-capital-cycle build {ticker}", language="bash")
    st.stop()

label, period_end, metrics = data.latest_metrics(view.quarterly)
st.caption(
    f"Source: SEC EDGAR XBRL Company Facts API. Data retrieved "
    f"{view.retrieved_at:%d %B %Y, %H:%M} UTC. Latest quarter: {label} "
    f"(ended {period_end:%d %B %Y})."
)

with st.container(horizontal=True, vertical_alignment="bottom"):
    window = st.segmented_control(
        "Quarters shown",
        list(QUARTER_WINDOWS),
        default="Last 12",
        required=True,
        key="capital_cycle_window",
    )
    hatch = st.toggle(
        "Hatch derived quarters",
        value=True,
        key="capital_cycle_hatch",
        help="Cash-flow statements are cumulative, so most quarters are year-to-date differences.",
    )

with st.container(horizontal=True):
    for metric in metrics:
        st.metric(
            f"{metric.label} ({label})",
            "n/a" if metric.value_bn is None else f"${metric.value_bn:,.1f}bn",
            delta=None
            if metric.year_ago_change is None
            else f"{metric.year_ago_change:+.0%} vs same quarter last year",
            delta_color="off",
            border=True,
            help=f"Basis: {metric.basis or 'missing'}.",
        )

figure = quarterly_cash_cycle_figure(
    data.limit_quarters(view.quarterly, QUARTER_WINDOWS[window]),
    company_name=view.company_name,
    note=view.note,
    dark=st.context.theme.type == "dark",
    hatch_derived=hatch,
)
with st.container(border=True):
    st.plotly_chart(figure, theme=None, width="stretch", config={"displaylogo": False})

with st.expander("Data table and download", icon=":material/table:"):
    table = data.display_table(view.quarterly)
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.NumberColumn(format="localized")
            for column in table.columns
            if column.endswith("(USD m)")
        },
    )
    st.download_button(
        "Download quarterly table (CSV, USD)",
        view.quarterly.to_csv(index=False),
        file_name=f"{view.ticker.lower()}_quarterly.csv",
        mime="text/csv",
        icon=":material/download:",
    )

with st.expander("Definitions and method", icon=":material/functions:"):
    st.markdown(
        "- **Base FCF** = operating cash flow - cash capex (cash purchases of property and "
        "equipment). This is a standardised measure calculated here, not a company-reported "
        "figure.\n"
        "- **Reported vs derived.** Income-statement items are reported per quarter. Cash-flow "
        "statements are cumulative from the start of the fiscal year and no filing reports the "
        "fourth quarter alone, so those quarters are differences of cumulative facts.\n"
        "- **Fiscal calendar.** Microsoft's fiscal year ends 30 June: FY26 Q1 is "
        "July-September 2025.\n"
        "- **First reported.** Where several filings report the same period, the earliest is "
        "used and later differing values are flagged in the data-quality panel.\n"
        "- **Missing is not zero.** A quarter with a missing component stays missing and shows "
        "as a gap.\n"
        "- **Not investment advice.** Educational research."
    )

with st.expander("Data quality and lineage", icon=":material/verified:"):
    counts = data.check_counts(view.checks)
    with st.container(horizontal=True):
        for status, count in counts.items():
            st.metric(status.capitalize(), count, border=True)
    attention = data.checks_needing_attention(view.checks)
    if attention.empty:
        st.success("No warnings or failures in the automated checks.", icon=":material/check:")
    else:
        st.warning("These checks need a look before relying on the affected quarters.")
        st.dataframe(attention, hide_index=True, width="stretch")

    st.markdown("**Series registered in `data/source_registry.csv`**")
    st.dataframe(
        view.lineage,
        hide_index=True,
        width="stretch",
        column_config={"source": st.column_config.LinkColumn("source")},
    )
    st.markdown(f"**SEC facts behind the latest quarter ({label})**")
    st.dataframe(
        view.filings,
        hide_index=True,
        width="stretch",
        column_config={
            "filing": st.column_config.LinkColumn("filing", display_text="Open filing index"),
            "value (USD)": st.column_config.NumberColumn(format="localized"),
        },
    )

st.caption("Educational research, not investment advice.")
