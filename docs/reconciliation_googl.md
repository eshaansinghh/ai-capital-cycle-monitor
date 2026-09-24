# Alphabet reconciliation against the filings

**Result: every figure compared matches the printed filings exactly, except two $1m rounding
differences that are recorded, not hidden.** This validates Alphabet's extraction, tag selection,
cumulative-to-quarter derivation and lease series. It does not validate any other company.

## Method

The filings below were downloaded from SEC EDGAR, stored unchanged and checksummed in the raw store,
and read with `ai-capital-cycle read-filing`: the **Consolidated Statements of Income** ("Total
revenues"), the **Consolidated Statements of Cash Flows** ("Net cash provided by operating
activities", "Purchases of property and equipment") and the **lease note**. Values are USD millions
as printed. They are recorded as constants in
[`tests/test_googl_real_data.py`](../tests/test_googl_real_data.py), which runs the pipeline on a
verbatim real-data fixture offline.

| Filing | Filed | Accession | SHA-256 (first 16) |
|---|---|---|---|
| Form 10-K, year ended 31 Dec 2025 | 2026-02-05 | 0001652044-26-000018 | `938c25cc7e2ea066` |
| Form 10-Q, quarter ended 30 Sep 2025 | 2025-10-30 | 0001652044-25-000091 | `99d6b263459897ff` |
| Form 10-Q, quarter ended 31 Mar 2026 | 2026-04-30 | 0001652044-26-000048 | `c346bfd89c5ba6fc` |
| Form 10-Q, quarter ended 30 Jun 2026 | 2026-07-23 | 0001652044-26-000071 | `1b4e671893d74a58` |
| Form 10-K, year ended 31 Dec 2018 (accounting-change text) | 2019-02-05 | 0001652044-19-000004 | `76a9b837cb3eb934` |

Fiscal quarters are calendar quarters, so FY26 Q2 is April-June 2026.

## A. Reported quarters

| Quarter | Line | Printed | Pipeline | Diff |
|---|---|---|---|---|
| FY26 Q1 | Total revenues | 109,896 | 109,896 | 0 |
| FY26 Q1 | Net cash from operating activities | 45,790 | 45,790 | 0 |
| FY26 Q1 | Purchases of property and equipment | 35,674 | 35,674 | 0 |
| FY25 Q1 (comparative) | revenue / OCF / capex | 90,234 / 36,150 / 17,197 | same | 0 |
| FY26 Q2 | Total revenues (three months) | 119,796 | 119,796 | 0 |
| FY25 Q2 | Total revenues (three months) | 96,428 | 96,428 | 0 |
| FY25 Q3 | Total revenues (three months) | 102,346 | 102,346 | 0 |

## B. Derived quarters (Alphabet prints cash flows cumulatively)

| Quarter | Line | Printed year-to-date figures | Derived | Pipeline | Diff |
|---|---|---|---|---|---|
| FY26 Q2 | Operating cash flow | six months 84,859 - Q1 45,790 | 39,069 | 39,069 | 0 |
| FY26 Q2 | Capex | six months 80,598 - Q1 35,674 | 44,924 | 44,924 | 0 |
| FY26 Q2 | Base FCF | 39,069 - 44,924 | -5,855 | -5,855 | 0 |
| FY25 Q4 | Revenue | 10-K 402,836 - nine months 289,007 | 113,829 | 113,829 | 0 |
| FY25 Q4 | Operating cash flow | 10-K 164,713 - nine months 112,311 | 52,402 | 52,402 | 0 |
| FY25 Q4 | Capex | 10-K 91,447 - nine months 63,596 | 27,851 | 27,851 | 0 |
| FY25 Q4 | Base FCF | 52,402 - 27,851 | 24,551 | 24,551 | 0 |

FY26 Q2 base FCF is negative because capex (44,924) exceeded operating cash flow (39,069).

## C. Cross-checks (four quarters against the printed year, and year-to-date sums)

| Check | Printed | Pipeline | Diff |
|---|---|---|---|
| FY2025 four quarters: revenue / OCF / capex | 402,836 / 164,713 / 91,447 | **402,837** / 164,713 / 91,447 | **+1 revenue (rounding)** |
| FY2024 four quarters | 350,018 / 125,299 / 52,535 | same | 0 |
| FY2023 four quarters | 307,394 / 101,746 / 32,251 | same | 0 |
| FY2025 nine months: revenue / OCF / capex | 289,007 / 112,311 / 63,596 | same | 0 |
| FY2026 six months | 229,692 / 84,859 / 80,598 | same | 0 |

**The two rounding differences.** Fiscal 2025 revenue: the four reported quarters sum to 402,837
against a printed 402,836, and the reported Q3 revenue (102,346) is 1m above the difference of the
nine-month and six-month figures (102,345). Both are within the rounding of figures reported in
millions, and the check output records them ("differ by rounding only"). They are not corrected.

## D. Lease note

| Period | Financing cash flows for finance leases (printed / pipeline) | Assets obtained (printed / pipeline) |
|---|---|---|
| FY26 Q1 | 522 / 522 | 211 / 211 |
| FY25 Q1 | 192 / 192 | 523 / 523 |
| FY26 Q2 | 318 / 318 | 691 / 691 |
| FY25 Q2 | 110 / 110 | 83 / 83 |
| FY25 Q3 | 92 / 92 | 383 / 383 |
| FY26 six months | 840 / 840 | 902 / 902 |
| FY25 nine months | 394 / 394 | 989 / 989 |
| FY25 Q4 = year - nine months | 1,988 - 394 = 1,594 / 1,594 | 1,606 - 989 = 617 / 617 |
| FY25 / FY24 four quarters | 1,988 / 405 | 1,606 / 313 |

The FY25 Q4 finance-lease figure is the quarter that carries the $1.1bn of prepayments for finance
leases not yet commenced that the filing's footnote attributes to 2025.

## What this does and does not show

- **Shows:** correct fact selection, period handling, cumulative differencing, Q4 derivation and
  lease series for Alphabet, on these periods and lines.
- **Does not show:** that XBRL is always faithful to the printed statements (both come from the same
  inline-XBRL document), or anything about other companies.
- **Coverage:** five filings were compared by hand across seven quarters and three fiscal years. The
  other quarters rely on the automated checks, which report 34 passes, 0 warnings, 0 failures and 3
  skipped items that are each explained (no standalone cash-flow quarters exist to compare, no sign
  expectation for operating cash flow, and lease disclosure starting at FY24 Q1).
