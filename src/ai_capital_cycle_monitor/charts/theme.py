"""Chart colour tokens.

Series hues were validated with the dataviz skill's validate_palette.js (all-pairs, both modes):
lightness band, chroma floor, protan/deutan separation, normal-vision floor and contrast all pass.
The headline series (base FCF) is a neutral ink line, so only two hues need to stay distinguishable.
Amber and red are reserved for warnings and are never used for a series.
"""

from dataclasses import dataclass

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"


@dataclass(frozen=True)
class ChartTheme:
    surface: str
    ink: str
    ink_secondary: str
    muted: str
    grid: str
    baseline: str
    operating_cash_flow: str
    cash_capex: str
    base_fcf: str


LIGHT = ChartTheme(
    surface="#fcfcfb",
    ink="#0b1f3a",
    ink_secondary="#52514e",
    muted="#898781",
    grid="#e1e0d9",
    baseline="#c3c2b7",
    operating_cash_flow="#2a78d6",
    cash_capex="#0f9d94",
    base_fcf="#0b1f3a",
)

DARK = ChartTheme(
    surface="#1a1a19",
    ink="#f2f5fa",
    ink_secondary="#c3c2b7",
    muted="#898781",
    grid="#2c2c2a",
    baseline="#383835",
    operating_cash_flow="#3987e5",
    cash_capex="#17a89d",
    base_fcf="#f2f5fa",
)


def theme_for(dark: bool) -> ChartTheme:
    return DARK if dark else LIGHT
