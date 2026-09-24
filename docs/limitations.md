# Limitations and data-risk register

This register records known constraints. Items marked **Open** are documented and deliberately
not solved yet. No number is invented to work around any of them.

## Future data risks (Open)

| ID | Risk | Detail | Planned handling | Phase |
|---|---|---|---|---|
| D1 | **European-bank data source** | Most candidate banks (for example UK and euro-area lenders) file only annual 20-F with the SEC, or nothing, so SEC-first sourcing will not give quarterly fundamentals. | Decide between annual-only cadence for this leg, or hand-curated investor-relations / ESEF-sourced figures labelled `company_ir`. May narrow the universe. | 4 |
| D2 | **GPU rental pricing** | No free, redistributable API. Specialist indices can be licensed or paywalled. Vendor list prices vary by GPU configuration, contract type, region and cluster size. | Manual, dated observations with source and contract type recorded. No scraping that breaches terms of use. Like-for-like comparison only. | 5 |
| D3 | **Private-company metrics** | ARR and user figures for private AI companies exist only as dated news reports or company statements, in incompatible units. | Manually maintained table, one cited row per figure, labelled reported/estimated. Never presented as audited revenue. Missing metrics stay "not publicly disclosed". | 5 |
| D4 | **Neocloud edge cases** | Filing history is short. Foreign private issuers file different forms under a different taxonomy. Backlog, contracted versus energised capacity, GPU collateral and customer concentration are inconsistently tagged. | Start with a US domestic filer. Treat foreign-filer neoclouds as a stretch item. Add issuer-specific field mappings. | 3, 5 |

## Known methodological limitations

- **FCF definitions differ by company** and have changed over time (for example the treatment of
  finance-lease principal). Reconciliation to filings is required, and company-specific mapping
  overrides are preferred to forcing inconsistent XBRL tags into one field.
- **Fiscal calendars differ** (Microsoft June, Oracle May, Nvidia January). Comparisons need an
  explicit alignment rule (see methodology section 9).
- **Total capex is not AI capex.** The project does not infer an AI share of capex.
- **Token consumption** is a published forecast used as a scenario anchor, not an observed series.
- **Aggregated price data** (for example Yahoo Finance) may carry adjustment and survivorship
  limitations. Retrieval dates are recorded and the source is tier 4.
- **Event studies** have weak identification when events are anticipated or overlap with other
  news. Results are "associated with", never "caused by" unless identification is strong.
- **Small samples**: few events and a short neocloud history limit statistical power.

## Operational constraints

- **SEC fair access:** every request needs a User-Agent with a real name and contact email (set in
  the local, gitignored `.env`), and requests must stay under the SEC rate limit.
- **FRED** requires a free personal API key (local `.env` only).
- **No investment advice.** This is educational research.
