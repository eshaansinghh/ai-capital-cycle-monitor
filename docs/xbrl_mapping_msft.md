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

## Caveat: cash capex is not total infrastructure investment

`PaymentsToAcquirePropertyPlantAndEquipment` is cash paid for property and equipment ("Additions to
property and equipment"). It **excludes assets acquired under finance leases**, which are reported
separately in the financing section and in the lease note. For a company building data-centre
capacity partly through finance leases, cash capex understates total infrastructure investment, and
base FCF overstates the cash left over relative to a lease-adjusted view. This is why the project
keeps **base FCF and lease-adjusted FCF as separate measures** (see
[`docs/methodology.md`](methodology.md)). Lease-adjusted FCF is not built in Phase 2, so no
conclusion about the capital cycle should rest on base FCF alone.

## Open items

- Finance-lease principal and other infrastructure financing payments are not yet mapped
  (Phase 3, for the lease-adjusted measure).
- Microsoft's non-GAAP "capital expenditures including finance leases" appears in earnings
  releases (company IR material), not in XBRL, and is not used here.
- Each new company needs its own `audit-tags` run before a mapping is written. Do not copy this
  mapping to another company.
