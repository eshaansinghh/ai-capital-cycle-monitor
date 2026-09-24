# Chart catalogue

**Status: figure 2 is built for Microsoft on real SEC data (Phase 2); all others are planned.** An
entry moves to "built" only when its data are traceable to `data/source_registry.csv`. The page
refuses to draw a series that is not registered.

Standard for every chart: title, unit, date range, source note, "as of" date, colour-blind
considerate palette, and PNG/CSV download where practical. Observed, guided, estimated, derived
and modelled values use different labels and visual styles. Pie or donut charts are used only
for a disclosed composition that sums to 100%.

| # | Figure | Visual | Decision it supports | Phase |
|---|---|---|---|---|
| 1 | Capital-cycle scorecard | Table with threshold flags | Where are risks building? | 3-4 |
| 2 | Quarterly capex, OCF and FCF by hyperscaler | Grouped bars and lines | Is spending outrunning internal cash generation? | 2, 3 |
| 3 | Reported-to-lease-adjusted FCF | Waterfall | How much do financing conventions change the picture? | 3 |
| 4 | Capex/revenue and capex/OCF | Small multiples | Who is spending most aggressively? | 3 |
| 5 | Revenue growth versus investment intensity | Scatter | Is heavier spending associated with stronger current growth? | 3 |
| 6 | Token-demand scenarios | Fan chart (anchors vs modelled path) | What adoption path is embedded in infrastructure demand? | 5 |
| 7 | H100/B200 rental prices by contract type | Lines | Is compute scarcity easing or persisting? | 5 |
| 8 | Neocloud growth versus leverage | Bubble chart (only with reliable filings) | Which growth models carry the most financing risk? | 5 |
| 9 | US mega-cap technology versus European banks | Valuation/profitability matrix | What is the opportunity cost of AI exposure? | 4 |
| 10 | Event-study cumulative abnormal returns | Line with confidence band | Did a selected event produce unusual returns? | 6 |
| 11 | Reverse-DCF sensitivity | Heatmap | What growth and margin outcomes justify the current value? | 4 |
| 12 | Source quality and freshness | Panel | How reliable and current is the evidence? | 3 |

## Figure 2: colour validation record

Series hues were checked with the dataviz skill's `validate_palette.js`, across all pairs, in both
modes. Lightness band, chroma floor, protan/deutan separation, normal-vision floor (>= 15) and
contrast against the surface all pass.

| Series | Light | Dark |
|---|---|---|
| Operating cash flow | `#2a78d6` | `#3987e5` |
| Capital expenditure | `#0f9d94` | `#17a89d` |
| Base free cash flow | navy ink `#0b1f3a` (neutral line) | `#f2f5fa` |

A first candidate set of muted navy, blue and teal failed on chroma, lightness band and
normal-vision separation, so a more saturated blue/teal pair replaced it. Amber and red are
reserved for warnings and are never used for a series. Bars whose value is derived from
year-to-date differences are hatched, and missing quarters are gaps, never zeros.

Checked on the real Microsoft data in a real browser, light and dark. With all 36 quarters the axis
labels shorten and rotate and the source note stays visible, after a collision between them was
found and fixed.
