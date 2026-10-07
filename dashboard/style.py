"""Shared visual design system for the dashboard.

Design direction: a restrained "professional analytics product"
look, in a dark and a light theme (closer to a modern data/SaaS dashboard than a hockey video game)
-- clean cards, a single muted accent color, crisp sans-serif type for
UI text and a monospace face reserved for numeric data, and small
transitions rather than glow/animation. Paired with
.streamlit/config.toml, whose [theme.dark] / [theme.light] sections set the
colors Streamlit's own widgets, buttons, and dataframes read directly; the
palettes below must match them.

Call apply_theme() once per page, right after st.set_page_config().
Use colors() for the active theme's palette in page code, and
style_chart(fig) on every Plotly figure so charts share the same
palette instead of Plotly's default colors. Wrap each section in
`with card(name):` and use section_label(text) for the heading that introduces a card/section.

Depth: page background -> section cards (a raised panel, visible border,
bold heading with an accent bar) -> metric tiles inside a section (inset
back down to the page color), so sections read as distinct blocks rather
than one field of numbers.
"""

import re

import streamlit as st

# One palette per theme. Page code reads the active one with colors() for
# anything CSS can't reach (e.g. a chart line color).
PALETTES = {
    "dark": {
        "bg": "#0a0d12",
        "panel": "#12161d",
        "panel_alt": "#171c24",
        "border": "rgba(255, 255, 255, 0.08)",
        "border_strong": "rgba(255, 255, 255, 0.16)",
        "text": "#e6e9ee",
        "text_muted": "#8892a0",
        "accent": "#3b82f6",
        "positive": "#22c55e",
        "negative": "#ef4444",
        "warning": "#f59e0b",
    },
    "light": {
        "bg": "#eef1f5",
        "panel": "#ffffff",
        "panel_alt": "#ffffff",
        "border": "rgba(15, 23, 42, 0.10)",
        "border_strong": "rgba(15, 23, 42, 0.20)",
        "text": "#111827",
        "text_muted": "#5b6472",
        "accent": "#2563eb",
        "positive": "#16a34a",
        "negative": "#dc2626",
        "warning": "#d97706",
    },
}


def theme_type() -> str:
    """'light' or 'dark' -- the theme this viewer's browser is showing
    (dark until the browser has reported one)."""
    return "light" if st.context.theme.type == "light" else "dark"


def colors() -> dict[str, str]:
    """The active theme's palette."""
    return PALETTES[theme_type()]

FONT_FAMILY = "'Inter', -apple-system, 'Segoe UI', sans-serif"
MONO_FAMILY = "'JetBrains Mono', ui-monospace, 'SFMono-Regular', monospace"

# A restrained, muted palette for multi-series charts -- no neon.
CHART_COLORWAY = ["#3b82f6", "#22c55e", "#f59e0b", "#a78bfa", "#ef4444", "#14b8a6"]

def _css(c: dict[str, str]) -> str:
    """The shared stylesheet, filled in with palette c."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_FAMILY};
}}

h1, h2, h3 {{
    font-family: {FONT_FAMILY} !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
    color: {c["text"]};
}}

h1 {{
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}}

p, span, label, li {{
    color: {c["text"]};
}}

/* Section heading: bold, full-brightness, with an accent bar so each
   card's title stands out from the numbers inside it. */
.section-heading {{
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: {c["text"]};
    border-left: 3px solid {c["accent"]};
    padding-left: 0.6rem;
    line-height: 1.2;
    margin-bottom: 0.5rem;
}}

/* Metric "cards" */
div[data-testid="stMetric"] {{
    background: {c["bg"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 14px 16px;
    transition: border-color 150ms ease;
}}
div[data-testid="stMetric"]:hover {{
    border-color: {c["border_strong"]};
}}
div[data-testid="stMetricLabel"] {{
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.7rem !important;
    font-weight: 600;
    color: {c["text_muted"]} !important;
}}
div[data-testid="stMetricValue"] {{
    font-family: {MONO_FAMILY};
    font-weight: 600;
    font-size: 1.75rem !important;
    color: {c["text"]};
}}
div[data-testid="stMetricDelta"] {{
    font-family: {MONO_FAMILY};
    font-weight: 500;
}}

/* Two metrics sharing one card (Team page special teams: last 10 games +
   season). The keyed container is the card; the metrics inside drop their
   own card styling, and the season one is smaller. */
div[class*="st-key-metric_pair_"] {{
    background: {c["bg"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 14px 16px;
}}
div[class*="st-key-metric_pair_"] div[data-testid="stMetric"] {{
    background: none;
    border: none;
    padding: 0;
}}
div[class*="st-key-metric_pair_"] div[class*="st-key-metric_secondary_"] div[data-testid="stMetricValue"] {{
    font-size: 1.25rem !important;
}}

/* Section cards, created with card() below. Styled by their key class
   because Streamlit 1.65 bordered containers have no stable selector
   of their own. */
div[class*="st-key-card_"] {{
    border: 1px solid {c["border_strong"]} !important;
    border-radius: 12px !important;
    background: {c["panel_alt"]};
    margin-bottom: 0.75rem;
}}

/* Buttons -- flat, with a small transition; primary/secondary colors
   otherwise come from config.toml's theme so a "primary"-typed button
   (used for an active tab/segmented control) reads as selected. */
.stButton > button {{
    border-radius: 8px;
    font-weight: 500;
    transition: filter 150ms ease, border-color 150ms ease;
    box-shadow: none !important;
}}
.stButton > button:hover {{
    filter: brightness(1.15);
}}

/* Filter controls -- labels and dropdowns styled to read as obvious,
   clickable controls rather than blending into the dark cards. */
div[data-testid="stWidgetLabel"] p {{
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: {c["text"]} !important;
}}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    background: {c["panel_alt"]};
    border: 1px solid rgba(59, 130, 246, 0.55) !important;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 150ms ease, box-shadow 150ms ease;
}}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{
    border-color: {c["accent"]} !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
}}
div[data-testid="stSelectbox"] svg {{
    color: {c["accent"]};
}}

/* Team picker: the header's logo button and the logo grid it opens.
   Streamlit sizes label images like text icons, so enlarge them here. */
.st-key-team_picker button {{
    padding: 4px 8px;
    min-height: 0;
}}
.st-key-team_picker button img {{
    height: 34px !important;
    max-height: none !important;
    width: auto;
}}
.st-key-team_picker_grid button img {{
    height: 30px !important;
    max-height: none !important;
    width: auto;
}}
.st-key-team_picker_grid button {{
    padding: 6px 4px;
}}

/* Home page artwork: centered, and no taller than what's left of the
   window under the title, so the page never needs scrolling. */
.st-key-home_hero {{
    align-items: center;
}}
.st-key-home_hero img {{
    max-height: calc(100vh - 260px);
    width: auto !important;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: {c["panel"]};
    border-right: 1px solid {c["border"]};
}}

/* Dataframes read as cards too */
div[data-testid="stDataFrame"] {{
    border: 1px solid {c["border"]};
    border-radius: 10px;
    overflow: hidden;
}}

hr {{
    border-color: {c["border"]} !important;
    margin: 1.4rem 0 !important;
}}
</style>
"""


def apply_theme() -> None:
    """Inject the dashboard's shared visual design system (in the active
    theme's colors) into the current page."""
    st.markdown(_css(colors()), unsafe_allow_html=True)


def card(name: str):
    """A section card: use as `with card("season_totals"):`. The name must be
    unique on the page -- it becomes the container key the CSS targets."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return st.container(border=True, key=f"card_{slug}")


def section_label(text: str) -> None:
    """The bold heading (with an accent bar) that introduces a card/section."""
    st.markdown(f'<div class="section-heading">{text}</div>', unsafe_allow_html=True)


def result_style(result: str) -> str:
    """Cell style for a game result like "W 3-2": colored by W/L/OT, bold.
    Use with DataFrame.style.map(result_style, subset=["result"])."""
    c = colors()
    result_colors = {"W": c["positive"], "L": c["negative"], "OT": c["warning"]}
    return f"color: {result_colors[result.split()[0]]}; font-weight: 700"


def style_chart(fig):
    """Apply the shared theme (active palette) + colorway to a Plotly figure."""
    c = colors()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",  # transparent: inherit the section card
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, color=c["text"], size=13),
        colorway=CHART_COLORWAY,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=c["border"], zerolinecolor=c["border_strong"], linecolor=c["border"])
    fig.update_yaxes(gridcolor=c["border"], zerolinecolor=c["border_strong"], linecolor=c["border"])
    return fig
