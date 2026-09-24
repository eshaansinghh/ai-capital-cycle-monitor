# Alphabet XBRL tag mapping: evidence and decisions

The mapping in [`config/xbrl_mappings.yml`](../config/xbrl_mappings.yml) was written from an audit of
Alphabet's real SEC Company Facts, retrieved 24 September 2026. Nothing was carried over from
Microsoft. Reproduce with `uv run ai-capital-cycle audit-tags GOOGL` (and `--pattern`).

## Tags found

| Field | Tag | Duration facts | Period ends | Decision |
|---|---|---|---|---|
| Revenue | `Revenues` | 74 | 2013-12-31 to 2026-06-30 | **Primary.** |
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 87 | 2016-12-31 to 2025-03-31 | Second candidate. |
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 99 | 2013-12-31 to 2026-06-30 | **Only tag.** |
| Capex | `PaymentsToAcquirePropertyPlantAndEquipment` | 119 | 2013-12-31 to 2026-06-30 | **Only tag.** |
| Finance-lease cash flows | `FinanceLeasePrincipalPayments` | 22 | 2022-12-31 to 2026-06-30 | Mapped from fiscal 2024. |
| Finance-lease assets obtained | `RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability` | 22 | 2022-12-31 to 2026-06-30 | Mapped from fiscal 2024. |

## Revenue: two tags, no conflict

From fiscal 2019 Alphabet reports total revenue under `Revenues` for some periods and under
`RevenueFromContractWithCustomerExcludingAssessedTax` for others (for example fiscal 2022 is
entirely the second tag, fiscal 2025 entirely the first). The coverage audit shows **zero tag
conflicts and zero later revisions** wherever both report, so the two are the same total revenue
under different tag choices. The priority order handles each period; the tag used is stored on every
observation.

## Where comparable history starts: fiscal 2017

Alphabet's own FY2018 10-K (accession 0001652044-19-000004) states that it adopted Topic 606
"Revenue from Contracts with Customers" **on 1 January 2017** using the modified retrospective
method: results for periods after that date are under Topic 606, while prior periods "are not
adjusted and continue to be reported in accordance with our historic accounting under Topic 605".
Alphabet therefore has an accounting break between 2016 and 2017 and none after it, so the history
starts in **fiscal 2017 (Q1 ended 31 March 2017)**, not 2018 as for Microsoft. The same 10-K says
Topic 842 (leases) is adopted on 1 January 2019 with comparatives not restated. That does not touch
revenue, operating cash flow or cash capex.

From fiscal 2017 every field has all four quarters, with zero tag conflicts and zero later revisions.

## Reported versus derived quarters

Alphabet's 10-Q cash-flow statements are **cumulative** (year to date), so no three-month cash-flow
facts exist after Q1. Operating cash flow and capex are reported for Q1 and derived for Q2-Q4 as
differences of year-to-date figures. Revenue is reported per quarter for Q1-Q3, with Q4 derived as
year minus nine months in every fiscal year (nine derived revenue quarters across fiscal 2017-2025).

## Rounding

Alphabet reports in millions. Rounding each figure to a million means a reported three-month value
can differ from a year-to-date difference by up to 1.5m, and four quarters can differ from the
reported year by up to 2.5m, with no error in the filing. Fiscal 2025 revenue shows exactly this: the
four quarters sum to 402,837m against a reported 402,836m, and Q3 differs from its year-to-date
difference by 1m. The checks apply a tolerance derived from the reporting unit and **record each
rounding-level difference** rather than hiding it (see `docs/methodology.md`).

## Lease and infrastructure financing

Alphabet's finance-lease activity is small next to its cash capex, but the disclosure has two
features that must not be smoothed over.

| USD millions (10-K FY2025 lease note) | 2023 | 2024 | 2025 |
|---|---|---|---|
| Purchases of property and equipment (cash capex) | 32,251 | 52,535 | 91,447 |
| Financing cash flows used for finance leases | 705 | 405 | 1,988 |
| Assets obtained in exchange for finance lease liabilities | 564 | 313 | 1,606 |

- **The finance-lease line is not pure principal.** The lease note's footnote says those flows "are
  included within financing activities as repayments of debt", and that 2025 "includes $1.1 billion
  of prepayments for finance leases not yet commenced". The mapped series
  `finance_lease_principal` is therefore Alphabet's disclosed **financing cash flows for finance
  leases**, and fiscal 2025 includes that prepayment, disclosed only as an annual amount and not
  allocable to quarters. The derived FY25 Q4 figure (1,594m = 1,988m - 394m) is the quarter that
  carries the difference between the year and nine months.
- **Disclosure starts late.** The lease tags first appear for the year ended 31 December 2022, and
  quarterly facts begin in fiscal 2024 (the 2022 and 2023 facts are annual only and cannot be split
  into quarters). Lease-adjusted FCF therefore exists only from **FY24 Q1**. Earlier quarters have
  base FCF and no lease-adjusted figure: they are reported as *not disclosed*, never as zero.
- **Other infrastructure financing payments:** reviewed and none disclosed. The Cash Flows
  Statements' financing section has stock-award payments, repurchases, dividends, debt issued and
  repaid, and sales of interests in consolidated entities only.
- **Scale:** assets obtained under finance leases were 1.8% of cash capex in 2025 (1,606m against
  91,447m). Compare Microsoft, where the same ratio is about 21%.

## Cash capex and unpaid purchases

The cash-flow statement discloses "Purchases of property and equipment included in accrued
liabilities and accounts payable" of 7,435m, 10,326m and 15,090m at the end of 2023, 2024 and 2025.
Cash capex records only what was paid, so it lags accrued capex. This is a disclosed balance, not a
series, and it is not adjusted for.

## Open items

- Alphabet's non-GAAP free cash flow (earnings releases) is company IR material and is not used.
- The fiscal 2025 prepayment cannot be attributed to quarters.
- Each remaining company gets its own audit. Do not reuse this mapping for another company.
