# Microsoft reconciliation against the filings

**Result: every figure compared matches the printed filings exactly (difference 0).** This validates
the pipeline's extraction, tag selection, period handling and Q4 derivation for Microsoft. It does
not validate other companies, which need their own reconciliation.

## Method

1. The three filings below were downloaded from SEC EDGAR and stored unchanged in the raw store
   (`data/raw/sec/filings/`, checksummed).
2. The visible statement text was read from each filing: the **Income Statements** (line "Total
   revenue") and the **Cash Flows Statements** (lines "Net cash from operations" and "Additions to
   property and equipment"), in USD millions as printed.
3. Those printed figures were compared with the pipeline's values built from the SEC Company Facts
   API, retrieved 24 September 2026.
4. The printed figures are recorded as constants in
   [`tests/test_msft_real_data.py`](../tests/test_msft_real_data.py), which runs the pipeline on a
   verbatim real-data fixture, so the comparison re-runs in CI without network access.

## Filings used

| Filing | Filed | Accession | Document | SHA-256 of stored copy (first 16) |
|---|---|---|---|---|
| Form 10-Q, quarter ended 30 September 2025 (fiscal 2026 Q1) | 2025-10-29 | 0001193125-25-256321 | [msft-20250930.htm](https://www.sec.gov/Archives/edgar/data/789019/000119312525256321/msft-20250930.htm) | `51cbcaecb8f370b5` |
| Form 10-Q, quarter ended 31 March 2026 (fiscal 2026 Q3) | 2026-04-29 | 0001193125-26-191507 | [msft-20260331.htm](https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm) | `721157b9d436868c` |
| Form 10-K, year ended 30 June 2026 (fiscal 2026) | 2026-07-29 | 0001193125-26-323660 | [msft-20260630.htm](https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm) | `96d03620b06dc4d1` |

## A. Reported quarters (USD millions)

| Quarter | Line | Printed | Pipeline | Difference | Source column |
|---|---|---|---|---|---|
| FY26 Q1 | Total revenue | 77,673 | 77,673 | 0 | Q1 10-Q, three months ended 30 Sep 2025 |
| FY26 Q1 | Net cash from operations | 45,057 | 45,057 | 0 | same |
| FY26 Q1 | Additions to property and equipment | (19,394) | 19,394 | 0 | same |
| FY26 Q3 | Total revenue | 82,886 | 82,886 | 0 | Q3 10-Q, three months ended 31 Mar 2026 |
| FY26 Q3 | Net cash from operations | 46,679 | 46,679 | 0 | same |
| FY26 Q3 | Additions to property and equipment | (30,876) | 30,876 | 0 | same |

Prior-year comparatives printed in the same filings also match: FY25 Q1 revenue 65,585, and FY25 Q3
revenue 70,066, operating cash flow 37,044 and capex 16,745. Capex is printed in brackets as an
outflow and stored as a positive outflow, per the sign convention in `config/metrics.yml`.

## B. Derived fourth quarter, fiscal 2026 (USD millions)

Q4 is not printed on its own, so it is the 10-K year minus the Q3 10-Q nine-month figure, from two
different filings.

| Line | 10-K year ended 30 Jun 2026 | Q3 10-Q nine months ended 31 Mar 2026 | Q4 = year - nine months | Pipeline Q4 | Difference |
|---|---|---|---|---|---|
| Total revenue | 331,839 | 241,832 | 90,007 | 90,007 | 0 |
| Net cash from operations | 182,935 | 127,494 | 55,441 | 55,441 | 0 |
| Additions to property and equipment | 115,948 | 80,146 | 35,802 | 35,802 | 0 |
| Base FCF (operating cash flow - capex) | | | 19,639 | 19,639 | 0 |

## C. Cross-checks

| Check | Printed | Pipeline | Difference |
|---|---|---|---|
| Fiscal 2026, four quarters summed: revenue / operating cash flow / capex | 331,839 / 182,935 / 115,948 | same | 0 |
| Fiscal 2025, four quarters summed | 281,724 / 136,162 / 64,551 | same | 0 |
| Fiscal 2024, four quarters summed | 245,122 / 118,548 / 44,477 | same | 0 |
| Fiscal 2026 Q1-Q3 summed | 241,832 / 127,494 / 80,146 | same | 0 |
| Fiscal 2025 Q1-Q3 capex summed | 47,472 | 47,472 | 0 |

The fiscal 2024 and 2025 totals come from the same 10-K's comparative columns, and they test the
period alignment and Q4 derivation across three fiscal years, not only the latest.

## What this does and does not show

- **Shows:** the pipeline reads the right facts, picks the right periods, applies the sign
  convention and derives Q4 correctly for these periods and lines.
- **Does not show:** that the XBRL in a filing is always faithful to its printed statements. The
  printed tables and the XBRL are from the same inline-XBRL document, so this is a check on the
  pipeline, not an audit of Microsoft.
- **Coverage:** three filings were compared by hand: the six reported-quarter lines in table A, the
  four prior-year comparatives, the derived Q4 in table B and the sums in table C. The other quarters
  rely on the automated checks (standalone versus cumulative agreement, quarters summing to each
  fiscal year, sign, revisions, tag conflicts and gaps), which all pass for all 36 quarters.
- **Reading step:** the printed values were extracted from the filings' text by a script and read by
  the analyst. Anyone can re-check them by opening the linked documents.

## Repeat it

```bash
uv run pytest tests/test_msft_real_data.py -q      # reruns the comparison on the real-data fixture
uv run ai-capital-cycle build MSFT                 # rebuilds from the stored SEC snapshot
```
