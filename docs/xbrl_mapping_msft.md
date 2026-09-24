# Microsoft XBRL tag mapping: evidence and decisions

The mapping in [`config/xbrl_mappings.yml`](../config/xbrl_mappings.yml) was written from an audit of
Microsoft's real SEC Company Facts, retrieved 24 September 2026 (see
[`data/source_registry.csv`](../data/source_registry.csv)). Nothing here is assumed. Reproduce it with:

```bash
uv run ai-capital-cycle audit-tags MSFT --pattern "revenue"   # discover candidate tags
uv run ai-capital-cycle audit-tags MSFT                        # tag coverage by fiscal year
```

## Tags found

| Field | Tag | Duration facts | Period ends | Decision |
|---|---|---|---|---|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 131 | 2016-06-30 to 2026-06-30 | **Primary.** |
| Revenue | `SalesRevenueNet` | 151 | 2009-06-30 to 2018-03-31 | Fallback, pre-2018 only. |
| Revenue | `Revenues` | 31 | 2007-09-30 to 2010-12-31 | Fallback, pre-2011 only. |
| Revenue | `SalesRevenueGoodsNet` | 26 | 2014-06-30 to 2018-03-31 | **Excluded.** A component (goods), not total revenue. |
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 167 | 2008-06-30 to 2026-06-30 | **Primary.** |
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` | 56 | 2012-06-30 to 2017-09-30 | Fallback, used only in fiscal 2014-2017. |
| Capex | `PaymentsToAcquirePropertyPlantAndEquipment` | 221 | 2008-06-30 to 2026-06-30 | **Only tag.** |

## Revenue changes basis in fiscal 2016-2017

Total revenue for the same fiscal year differs between the tag used before and after the accounting
change, and the old tag later gets revised:

| Fiscal year | `SalesRevenueNet` as originally filed | `RevenueFromContract...` as recast |
|---|---|---|
| 2016 (to 30 Jun 2016) | 85,320m (10-K filed 2016-07-28) | 91,154m (10-K filed 2018-08-03) |
| 2017 (to 30 Jun 2017) | 89,950m (10-K filed 2017-08-02) | 96,571m (10-K filed 2018-08-03) |
| 2018 (to 30 Jun 2018) | not reported | 110,360m (10-K filed 2018-08-03) |

In the coverage audit, fiscal 2016 and 2017 show **tag conflicts** (recast and original values
disagree) and fiscal 2017 shows **later revisions** under the old tag. From fiscal 2018 one tag
supplies every fact, with zero conflicts and zero revisions. Building a quarter from a fiscal-year
total on one basis and a nine-month figure on the other would give a wrong fourth quarter, so the
history starts in fiscal 2018 (`first_fiscal_year: 2018`). The alternative, silently preferring one
tag, would have hidden a real comparability break.

## Coverage by fiscal year (selected facts per tag)

| Fiscal years | Revenue | Operating cash flow | Capex |
|---|---|---|---|
| 2008-2010 | `Revenues`, then `SalesRevenueNet` | plain tag | one tag |
| 2011-2015 | `SalesRevenueNet` | plain tag (2014-2015 continuing-operations variant) | one tag |
| 2016-2017 | mixed, with conflicts | mixed (2016-2017) | one tag |
| **2018-2026** | **`RevenueFromContract...` only** | **plain tag only** | **one tag** |

## Selection rules

- **Priority order.** For each exact period the first candidate that reports it is used. The tag
  chosen is stored on every observation.
- **First reported.** If several filings report the same period, the earliest filing is used. Later
  filings with a different value are flagged as revisions, not substituted.
- **Conflicts are flagged.** A lower-priority tag reporting a different value for the same period is
  recorded, never ignored.
- **Periods come from dates**, not the filing's `fy`/`fp` labels. Those describe the filing, so a
  prior-year comparative carries the current filing's labels.

## Reported versus derived quarters

Microsoft's 10-Qs print three-month figures for income-statement and cash-flow lines, so Q1-Q3 are
used as reported. No filing prints the fourth quarter alone in the annual report, so Q4 is derived
as the fiscal-year total minus the nine-month year-to-date figure. Revenue's Q4 was reported
directly for fiscal 2018-2020 and is derived from fiscal 2021. The fourth quarters of operating
cash flow and capex are derived in every fiscal year.

## Lease and infrastructure financing (Phase 3)

Microsoft funds infrastructure through cash purchases of property and equipment **and** through
finance leases. Both are visible in the filings, and they are very different sizes:

| Item (fiscal year, USD millions, as printed in the 10-K lease note) | FY24 | FY25 | FY26 |
|---|---|---|---|
| Additions to property and equipment (cash capex) | 44,477 | 64,551 | 115,948 |
| Financing cash flows from finance leases (principal paid) | 1,286 | 2,283 | 3,101 |
| Assets obtained under finance leases (non-cash) | 11,633 | 20,511 | 24,608 |

- **`finance_lease_principal`** is mapped to `FinanceLeasePrincipalPayments` (the lease note's
  "Financing cash flows from finance leases"). It is **not** a Cash Flows Statement line: the
  financing section lists debt, stock issued and repurchased, dividends and "Other, net" only, so
  the principal sits inside "Other, net". Six facts per fiscal year, no conflicts or revisions.
- **`finance_lease_assets_acquired`** is mapped to
  `RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability` (the lease note's "Finance leases"
  under assets obtained in exchange for lease obligations). It is non-cash and covers every asset
  class Microsoft leases, not only data-centre equipment.
- **Other infrastructure financing payments:** reviewed and none disclosed (see
  `lease_adjustments` in the mapping). This is a documented finding, not an assumption of zero.

**Reading the two lease measures.** `lease_adjusted_fcf` follows the methodology definition (base
FCF less finance-lease *principal paid*), so it is a cash measure and barely differs from base FCF:
fiscal 2026 Q4 base FCF is 19,639m and lease-adjusted FCF is 18,717m. The much larger effect is on
the investment side: fiscal 2026 assets obtained under finance leases (24,608m) equal about a fifth
of cash capex (115,948m), and they create future principal payments that the cash measure has not
yet recorded. The supplementary `capex_incl_finance_leases` (cash capex plus assets obtained under
finance leases) shows that scale, and it is labelled an upper bound because the lease figure is not
limited to data-centre assets. Neither series alone says how much of the buildout is AI-specific.

## Open items

- Whatever is inside "Other, net" beyond finance-lease principal is not disclosed and is not
  adjusted for.
- Microsoft's non-GAAP "capital expenditures including finance leases" appears in earnings
  releases (company IR material), not in XBRL, and is not used here.
- Each new company needs its own `audit-tags` run before a mapping is written. Do not copy this
  mapping to another company.
