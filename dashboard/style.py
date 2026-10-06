"""Shared visual design system for the dashboard.

Design direction: a dark, restrained "professional analytics product"
look (closer to a modern data/SaaS dashboard than a hockey video game)
-- clean cards, a single muted accent color, crisp sans-serif type for
UI text and a monospace face reserved for numeric data, and small
transitions rather than glow/animation. Paired with
.streamlit/config.toml, which sets the base theme colors that
Streamlit's own widgets, buttons, and dataframes read directly.

Call apply_theme() once per page, right after st.set_page_config().
Use style_chart(fig) on every Plotly figure so charts share the same
palette instead of Plotly's default colors. Use section_label(text)
for the small uppercase heading that introduces a card/section.
"""

import streamlit as st

# Exported so page code can reuse the same palette for anything CSS
# can't reach (e.g. conditional text color in an f-string).
COLORS = {
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
}

FONT_FAMILY = "'Inter', -apple-system, 'Segoe UI', sans-serif"
MONO_FAMILY = "'JetBrains Mono', ui-monospace, 'SFMono-Regular', monospace"

# A restrained, muted palette for multi-series charts -- no neon.
CHART_COLORWAY = ["#3b82f6", "#22c55e", "#f59e0b", "#a78bfa", "#ef4444", "#14b8a6"]

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_FAMILY};
}}

h1, h2, h3 {{
    font-family: {FONT_FAMILY} !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
    color: {COLORS["text"]};
}}

h1 {{
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}}

p, span, label, li {{
    color: {COLORS["text"]};
}}

.eyebrow {{
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
    font-weight: 600;
    color: {COLORS["text_muted"]};
    margin-bottom: 0.35rem;
}}

/* Metric "cards" */
div[data-testid="stMetric"] {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 14px 16px;
    transition: border-color 150ms ease;
}}
div[data-testid="stMetric"]:hover {{
    border-color: {COLORS["border_strong"]};
}}
div[data-testid="stMetricLabel"] {{
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.7rem !important;
    font-weight: 600;
    color: {COLORS["text_muted"]} !important;
}}
div[data-testid="stMetricValue"] {{
    font-family: {MONO_FAMILY};
    font-weight: 600;
    font-size: 1.75rem !important;
    color: {COLORS["text"]};
}}
div[data-testid="stMetricDelta"] {{
    font-family: {MONO_FAMILY};
    font-weight: 500;
}}

/* Bordered containers (st.container(border=True)) read as cards */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 12px !important;
    border-color: {COLORS["border"]} !important;
    background: {COLORS["panel"]};
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
    color: {COLORS["text"]} !important;
}}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    background: {COLORS["panel_alt"]};
    border: 1px solid rgba(59, 130, 246, 0.55) !important;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 150ms ease, box-shadow 150ms ease;
}}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{
    border-color: {COLORS["accent"]} !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
}}
div[data-testid="stSelectbox"] svg {{
    color: {COLORS["accent"]};
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

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: {COLORS["panel"]};
    border-right: 1px solid {COLORS["border"]};
}}

/* Dataframes read as cards too */
div[data-testid="stDataFrame"] {{
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    overflow: hidden;
}}

hr {{
    border-color: {COLORS["border"]} !important;
    margin: 1.4rem 0 !important;
}}
</style>
"""


def apply_theme() -> None:
    """Inject the dashboard's shared visual design system into the current page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def section_label(text: str) -> None:
    """A small uppercase label introducing a card/section, e.g. 'SEASON SNAPSHOT'."""
    st.markdown(f'<div class="eyebrow">{text}</div>', unsafe_allow_html=True)


def style_chart(fig):
    """Apply the shared dark theme + colorway to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font=dict(family=FONT_FAMILY, color=COLORS["text"], size=13),
        colorway=CHART_COLORWAY,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border_strong"], linecolor=COLORS["border"])
    fig.update_yaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border_strong"], linecolor=COLORS["border"])
    return fig
