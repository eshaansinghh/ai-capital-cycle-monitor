# Methodology

> **Status:** frozen on 24 September 2026, before any data retrieval or analysis. The Git history
> is the evidence of this ordering. Changes after this point are made in new commits and are
> listed under [Amendments](#amendments), never edited silently.

## 1. Central question

Are public markets pricing the AI capital cycle faster than cash flows, utilisation and
monetisation can justify, and where is the better risk-adjusted opportunity across US AI leaders,
AI infrastructure providers and European banks?

"Bubble" is not tested as a single label. It is decomposed into four questions:

1. **Technology:** is AI adoption and token demand real?
2. **Economics:** is demand translating into revenue, margins and cash returns?
3. **Capital cycle:** is infrastructure supply growing faster than monetisable demand?
4. **Market pricing:** do valuations already assume unusually strong future outcomes?

The project reports the strongest evidence for and against the bubble reading. A result that
contradicts the bubble narrative is a valid result.

## 2. Pre-registered hypotheses

| ID | Hypothesis | Test | Evidence that would count against it |
|---|---|---|---|
| H1 | AI infrastructure spending is rising faster than near-term internally generated cash. | Compare capex growth with operating cash flow and FCF growth, by company and fiscal quarter. | Capex growth at or below operating cash flow growth across the universe, with FCF stable or rising. |
| H2 | Companies with stronger AI monetisation show better revenue revisions or segment growth. | Compare disclosed cloud and AI proxies with segment growth. Label proxy quality. | No relationship between the proxies and segment growth, or a relationship driven by one company. |
| H3 | Falling GPU rental rates indicate improving supply but may pressure infrastructure returns. | Track like-for-like hourly rental prices by chip, provider tier and contract type. | Like-for-like prices flat or rising over the observed period. |
| H4 | AI-exposed equities embed more demanding expectations than European banks. | Compare valuation, profitability, growth and reverse-DCF requirements. | Reverse-DCF requirements for AI leaders no more demanding than for the bank comparators. |
| H5 | Material AI regulatory or safety disclosures produce abnormal returns in exposed stocks. | Market-model event studies with several windows, benchmarks and placebo dates. | Abnormal returns indistinguishable from placebo dates. Insignificant results are reported. |
| H6 | Neocloud growth offers upside but carries financing, customer-concentration and utilisation risk. | Compare revenue, backlog/RPO, active capacity, capex, debt, interest and cash flow. | Neocloud growth funded predominantly from operating cash flow with low leverage and diversified customers. |

Hypotheses are propositions to test, not desired conclusions. Inference uses 95% confidence
intervals and two-sided tests at the 5% level. Results are reported whether or not they are
significant, and language stays at "associated with" unless identification is defensible.

## 3. Universe

Defined in [`config/companies.yml`](../config/companies.yml), which is the source of truth:

- **Hyperscalers and platforms:** Microsoft, Alphabet, Amazon, Meta, Oracle.
- **Infrastructure reference:** Nvidia.
- **Neocloud:** CoreWeave (short public filing history).
- **European banks:** deferred to Phase 4. Universe configurable in YAML. See
  [limitations](limitations.md).

## 4. Metric definitions

Defined in [`config/metrics.yml`](../config/metrics.yml). Summary:

| Metric | Formula |
|---|---|
| Base FCF | `operating_cash_flow - cash_capex` |
| Lease-adjusted FCF | `base_fcf - finance_lease_principal - other_infrastructure_financing_payments` (where disclosed) |
| Capital intensity | `cash_capex / revenue` |
| Cash reinvestment rate | `cash_capex / operating_cash_flow` |
| FCF margin | `base_fcf / revenue` |
| Incremental cash conversion | `change_in_fcf / change_in_revenue` |
| FCF yield | `ltm_fcf / market_cap` |
| Net debt | `total_debt - cash_and_short_term_investments` (lease liabilities shown separately) |

Rules that apply to every metric:

- Company-reported, standardised and lease-adjusted FCF are kept in separate columns.
- **Missing is not zero.** If an input is missing the metric is missing. A disclosed zero is zero.
- A metric is missing, never infinite or zero, when its denominator is zero.
- Total capex is not relabelled "AI capex". AI capex is used only when a company quantifies it.
  Management commentary is presented separately.

## 5. AI Capital Cycle Scorecard

Raw metrics come first. No composite "bubble score" is published in v1.

| Pillar | Example measures |
|---|---|
| Valuation | P/E, EV/sales, FCF yield, reverse-DCF growth requirement |
| Investment intensity | Capex/revenue, capex/OCF, capex growth |
| Monetisation | Cloud growth, AI-linked revenue disclosures, backlog/RPO |
| Cash conversion | FCF margin, incremental FCF per incremental revenue |
| Capacity economics | GPU rental price, utilisation proxy, power capacity |
| Financing quality | Net cash/debt, leases, interest coverage, stock compensation |
| Market concentration | Index weight, return contribution, correlation |

If a composite is added later, its formula, direction, weights, winsorisation and sensitivity
analysis are published, and the underlying values stay inspectable.

## 6. Data classification and sources

Every value is labelled with one basis: `reported`, `company_guided`, `consensus_estimated`,
`derived` or `scenario_modelled`. These are never blended and are visually distinct in charts.

Source priority: (1) SEC EDGAR, company filings and investor relations; FRED/ALFRED, ECB and
official statistics; regulators and official releases; (2) peer-reviewed papers, recognised
research organisations, established newswires, public institutional research; (3) transparent
specialist datasets; (4) aggregated price APIs, with retrieval date and limitations disclosed.
Lineage for each series is recorded in [`data/source_registry.csv`](../data/source_registry.csv).

## 7. Event-study specification

- Estimation window: trading days -250 to -30.
- Primary event window [-1, +1]. Robustness windows [0, +1], [-3, +3], [-5, +5].
- Market model first, against a broad-market and a relevant sector benchmark. Fama-French factors
  are an extension.
- Reported: abnormal return, CAR, standard error, t-statistic, confidence interval.
- Event dating: first public release timestamp. After-hours and weekend disclosures move to the
  next trading session under a documented exchange-calendar rule.
- Controls: confounder log (earnings, guidance, launches, macro releases, other legal news),
  anticipation flag, unaffected-peer comparison where possible, placebo dates.

## 8. Scenario and token-demand rules

- Published forecasts (for example a bank's token-consumption forecast) are **scenario anchors**,
  not observed time series. Interpolated points are labelled "modelled path from published
  endpoints", with the method stated.
- Implied revenue or compute is shown only when the user supplies an explicit price-per-token
  assumption.
- Private-company ARR is a dated, reported snapshot with uncertainty, not audited revenue.
  Weekly users, monthly users, enterprise seats, API customers and agent sessions are never
  combined. Undisclosed metrics are shown as "not publicly disclosed".

## 9. Open definitional questions

Resolved in the phase named, with the decision recorded under [Amendments](#amendments).

| Question | Phase | Current proposal |
|---|---|---|
| Which FCF variant is the headline when definitions diverge? | 3 | Show both everywhere. Headline is standardised base FCF because lease-adjusted FCF may be missing where components are undisclosed. |
| What is each company's AI-linked revenue proxy? | 3 | Per-company mapping table with a proxy-quality label. Segment names are not treated as equivalent across companies. |
| How are non-December fiscal calendars compared (Microsoft June, Oracle May, Nvidia January)? | 3 | Align by fiscal-quarter end date to the nearest calendar quarter-end. Never split or interpolate a fiscal quarter, and always display the fiscal label. |
| Market-cap date for FCF yield. | 3 | Market capitalisation at the period-end date, with the date shown. |
| Currency conversion for non-USD comparators. | 4 | Convert with a documented official rate series and show the local-currency series alongside. |

## Amendments

None yet.
