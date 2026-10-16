"""Shared visual design system for the dashboard.

Design direction: an "ice rink" analytics product in navy / blue / ice
blue -- a dark navy sidebar with rink markings, gradient italic page
titles, light content cards with a blue top edge and soft blue glow,
crisp sans-serif type for UI text and a monospace face reserved for
numeric data. The Home page hero is the boldest use of it. Paired with
.streamlit/config.toml, whose [theme] section sets the colors Streamlit's
own widgets, buttons, and dataframes read directly; the palette below must
match it.

Call apply_theme() once per page, right after st.set_page_config().
Use colors() for the palette in page code, and
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

# Page code reads this with colors() for anything CSS can't reach (e.g. a
# chart line color).
PALETTE = {
    "bg": "#eef4fb",
    "panel": "#ffffff",
    "panel_alt": "#ffffff",
    "border": "rgba(15, 23, 42, 0.10)",
    "border_strong": "rgba(15, 23, 42, 0.20)",
    "text": "#111827",
    "text_muted": "#5b6472",
    "accent": "#2563eb",
    "accent_light": "#38bdf8",
    "navy": "#0a1f4d",
    "positive": "#16a34a",
    "negative": "#dc2626",
    "warning": "#d97706",
}


def colors() -> dict[str, str]:
    """The dashboard's color palette."""
    return PALETTE

FONT_FAMILY = "'Inter', -apple-system, 'Segoe UI', sans-serif"
MONO_FAMILY = "'JetBrains Mono', ui-monospace, 'SFMono-Regular', monospace"

# A restrained, muted palette for multi-series charts -- no neon.
CHART_COLORWAY = ["#2563eb", "#38bdf8", "#0a1f4d", "#f59e0b", "#a78bfa", "#14b8a6"]

# Rink markings for the sidebar background (an SVG data URI): a blue line,
# the dashed center line and the center-ice circle.
SIDEBAR_RINK = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 260'>"
    "<line x1='0' y1='60' x2='300' y2='60' stroke='rgba(56,189,248,0.35)' stroke-width='8'/>"
    "<line x1='0' y1='170' x2='300' y2='170' stroke='rgba(186,230,253,0.15)' stroke-width='3' stroke-dasharray='8 6'/>"
    "<circle cx='150' cy='170' r='62' fill='none' stroke='rgba(186,230,253,0.22)' stroke-width='2'/>"
    "<circle cx='150' cy='170' r='4' fill='rgba(186,230,253,0.4)'/>"
    "</svg>"
)


def _css(c: dict[str, str]) -> str:
    """The shared stylesheet, filled in with palette c."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_FAMILY};
}}

header[data-testid="stHeader"] {{
    background: transparent;
}}

.stApp {{
    background:
        radial-gradient(900px 400px at 100% 0%, rgba(56, 189, 248, 0.14), transparent 70%),
        radial-gradient(700px 360px at 0% 100%, rgba(37, 99, 235, 0.08), transparent 70%),
        {c["bg"]};
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
    border-left: 3px solid transparent;
    border-image: linear-gradient(180deg, {c["accent"]}, {c["accent_light"]}) 1;
    padding-left: 0.6rem;
    line-height: 1.2;
    margin-bottom: 0.5rem;
}}

/* Metric "cards" */
div[data-testid="stMetric"] {{
    background: linear-gradient(160deg, #f5f9ff, #eaf3fd);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 10px;
    padding: 14px 16px;
    transition: border-color 150ms ease;
}}
div[data-testid="stMetric"]:hover {{
    border-color: rgba(56, 189, 248, 0.6);
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
    color: {c["navy"]};
}}
div[data-testid="stMetricDelta"] {{
    font-family: {MONO_FAMILY};
    font-weight: 500;
}}

/* Two metrics sharing one card (Team page special teams: last 10 games +
   season). The keyed container is the card; the metrics inside drop their
   own card styling, and the season one is smaller. */
div[class*="st-key-metric_pair_"] {{
    background: linear-gradient(160deg, #f5f9ff, #eaf3fd);
    border: 1px solid rgba(56, 189, 248, 0.28);
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
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(56, 189, 248, 0.30) !important;
    border-radius: 14px !important;
    background: {c["panel_alt"]};
    margin-bottom: 0.75rem;
    box-shadow: 0 10px 30px -18px rgba(11, 42, 107, 0.35);
}}
div[class*="st-key-card_"]::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, {c["navy"]}, {c["accent"]}, {c["accent_light"]});
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
   clickable controls rather than blending into the cards. */
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

/* Home page -- the one place the restrained look gives way to a bolder,
   ice-rink theme in navy / blue / ice blue.
   Wordmark: heavy italic SHL in a blue gradient, with "Sean's Hockey
   League" in small caps underneath. */
.brand {{
    display: flex;
    align-items: center;
    gap: 0.9rem;
    padding: 0.4rem 0 0.9rem;
}}
.brand-word {{
    font-size: 3.1rem;
    font-weight: 800;
    font-style: italic;
    letter-spacing: 0.01em;
    line-height: 1;
    padding-right: 0.15em;
    background: linear-gradient(100deg, #0a1f4d 0%, #1d4ed8 45%, #38bdf8 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    filter: drop-shadow(0 2px 10px rgba(56, 189, 248, 0.35));
    position: relative;
}}
.brand-word::after {{
    content: "";
    position: absolute;
    left: 0.1em;
    right: 0.3em;
    bottom: -0.18em;
    height: 4px;
    border-radius: 2px;
    transform: skewX(-20deg);
    background: linear-gradient(90deg, #1d4ed8, #38bdf8, rgba(56, 189, 248, 0));
}}
.brand-word--page {{
    font-size: 2.3rem;
}}
.brand--stacked {{
    flex-direction: column;
    align-items: flex-start;
    gap: 0;
}}
.brand-sub {{
    margin-top: 0.75rem;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #0369a1;
}}

/* Hero: a dark navy "rink" panel with blue-line markings, a soft glow,
   a slow light sweep, and a zoomed-in action photo on the right that
   fades into the navy. */
.hero {{
    position: relative;
    overflow: hidden;
    border-radius: 18px;
    min-height: 300px;
    margin: 0.25rem 0 1.6rem;
    background:
        radial-gradient(circle at 15% 0%, rgba(56, 189, 248, 0.25), transparent 45%),
        linear-gradient(120deg, #06122e 0%, #0b2a6b 55%, #1456b8 100%);
    border: 1px solid rgba(56, 189, 248, 0.35);
    box-shadow: 0 18px 40px -18px rgba(11, 42, 107, 0.65), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}}
.hero-rink {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    /* markings fade in from the right so they never run behind the text */
    -webkit-mask-image: linear-gradient(90deg, transparent 15%, #000 70%);
    mask-image: linear-gradient(90deg, transparent 15%, #000 70%);
}}
.hero-glow {{
    position: absolute;
    right: 6%;
    top: 50%;
    width: 320px;
    height: 320px;
    transform: translateY(-50%);
    background: radial-gradient(circle, rgba(56, 189, 248, 0.45), transparent 65%);
    filter: blur(8px);
}}
.hero-sweep {{
    position: absolute;
    inset: 0;
    background: linear-gradient(105deg, transparent 40%, rgba(186, 230, 253, 0.10) 50%, transparent 60%);
    background-size: 250% 100%;
    animation: hero-sweep 7s ease-in-out infinite;
}}
@keyframes hero-sweep {{
    0% {{ background-position: 120% 0; }}
    100% {{ background-position: -120% 0; }}
}}
@media (prefers-reduced-motion: reduce) {{
    .hero-sweep {{ animation: none; }}
}}
.hero-content {{
    position: relative;
    z-index: 1;
    padding: 2.4rem 2.6rem;
    max-width: 62%;
}}
.hero-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #bae6fd;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.45);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    margin-bottom: 1.1rem;
}}
.hero-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
}}
.hero-headline {{
    font-size: 2.5rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.08;
    color: #ffffff;
    margin-bottom: 0.9rem;
}}
.hero-headline span {{
    background: linear-gradient(90deg, #7dd3fc, #38bdf8);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}}
.hero .hero-lede {{
    color: rgba(224, 242, 254, 0.82) !important;
    font-size: 1rem;
    max-width: 28rem;
    margin-bottom: 1rem;
}}
.hero-meta {{
    font-family: {MONO_FAMILY};
    font-size: 0.75rem;
    color: rgba(186, 230, 253, 0.7);
}}
/* The photo is 1296x729; scaling it to 165% of its box and anchoring it
   top-right zooms in on the shooter, the goalie and the puck. */
.hero-photo {{
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 60%;
    background-repeat: no-repeat;
    background-size: 165% auto;
    background-position: 100% 8%;
    filter: saturate(1.15) contrast(1.05);
    -webkit-mask-image: linear-gradient(90deg, transparent 0%, rgba(0, 0, 0, 0.6) 25%, #000 50%);
    mask-image: linear-gradient(90deg, transparent 0%, rgba(0, 0, 0, 0.6) 25%, #000 50%);
}}
/* Ice-blue tint over the photo so the white ice matches the theme. */
.hero-photo::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(11, 42, 107, 0.55), rgba(56, 189, 248, 0.18));
    mix-blend-mode: multiply;
}}
.hero-credit {{
    position: absolute;
    z-index: 1;
    right: 14px;
    bottom: 10px;
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    color: rgba(255, 255, 255, 0.85);
    text-shadow: 0 1px 4px rgba(6, 18, 46, 0.8);
}}
@media (max-width: 900px) {{
    .hero-content {{ max-width: 100%; }}
    .hero-photo, .hero-credit, .hero-glow {{ display: none; }}
}}

/* Explore cards: white with a blue gradient top edge; lift and glow on hover. */
.explore-label {{
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #0369a1;
    margin-bottom: 0.6rem;
}}
div[class*="st-key-explore_"] {{
    position: relative;
    background: {c["panel"]};
    border: 1px solid rgba(56, 189, 248, 0.30);
    border-radius: 14px;
    padding: 1.1rem 1.1rem 0.9rem;
    overflow: hidden;
    gap: 0.2rem;
    transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}}
div[class*="st-key-explore_"]::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #1d4ed8, #38bdf8);
}}
div[class*="st-key-explore_"]:hover {{
    transform: translateY(-3px);
    border-color: rgba(56, 189, 248, 0.7);
    box-shadow: 0 12px 28px -12px rgba(29, 78, 216, 0.45);
}}
div[class*="st-key-explore_"] a span[data-testid="stIconMaterial"] {{
    color: #38bdf8;
}}
div[class*="st-key-explore_"] a p {{
    font-size: 1.05rem;
    color: #0a1f4d !important;
}}

/* Sidebar: a navy "rink" panel -- glow at the top, faint blue line and
   center-ice circle near the bottom, the SHL wordmark above the page
   links, numbered links, and the current page lit up in ice blue. */
section[data-testid="stSidebar"] {{
    background:
        url("{SIDEBAR_RINK}") no-repeat center bottom / 100% auto,
        radial-gradient(circle at 0% 0%, rgba(56, 189, 248, 0.28), transparent 55%),
        linear-gradient(180deg, #06122e 0%, #0b2a6b 70%, #0f3c8c 100%);
    border-right: 1px solid rgba(56, 189, 248, 0.35);
}}
[data-testid="stSidebarHeader"] {{
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    height: auto;
    padding-top: 1.6rem;
    padding-bottom: 0.6rem;
}}
[data-testid="stSidebarHeader"]::after {{
    content: "Sean's Hockey League";
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: rgba(125, 211, 252, 0.75);
    margin-top: 0.15rem;
}}
[data-testid="stSidebarHeader"] [data-testid="stLogoSpacer"] {{
    display: none;
}}
[data-testid="stSidebarHeader"]::before {{
    content: "SHL";
    font-size: 2rem;
    font-weight: 800;
    font-style: italic;
    letter-spacing: 0.01em;
    padding-right: 0.15em;
    background: linear-gradient(100deg, #ffffff 10%, #7dd3fc 60%, #38bdf8 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    filter: drop-shadow(0 0 12px rgba(56, 189, 248, 0.45));
}}
[data-testid="stSidebarNavItems"] {{
    counter-reset: navlink;
}}
a[data-testid="stSidebarNavLink"] {{
    counter-increment: navlink;
    border-radius: 10px;
    border: 1px solid transparent;
    margin: 2px 0;
    transition: background 150ms ease, border-color 150ms ease;
}}
a[data-testid="stSidebarNavLink"]::before {{
    content: counter(navlink, decimal-leading-zero);
    font-family: {MONO_FAMILY};
    font-size: 0.7rem;
    color: rgba(125, 211, 252, 0.6);
    margin-right: 0.7rem;
}}
a[data-testid="stSidebarNavLink"] p,
a[data-testid="stSidebarNavLink"] span {{
    color: rgba(224, 242, 254, 0.78) !important;
    font-weight: 500;
}}
a[data-testid="stSidebarNavLink"]:hover {{
    background: rgba(56, 189, 248, 0.10) !important;
    border-color: rgba(56, 189, 248, 0.30);
}}
a[data-testid="stSidebarNavLink"][aria-current="page"] {{
    background: linear-gradient(90deg, rgba(56, 189, 248, 0.28), rgba(56, 189, 248, 0.06)) !important;
    border-color: rgba(56, 189, 248, 0.55);
    box-shadow: 0 0 18px -6px rgba(56, 189, 248, 0.7), inset 3px 0 0 #38bdf8;
}}
a[data-testid="stSidebarNavLink"][aria-current="page"]::before {{
    color: #38bdf8;
}}
a[data-testid="stSidebarNavLink"][aria-current="page"] p,
a[data-testid="stSidebarNavLink"][aria-current="page"] span {{
    color: #ffffff !important;
    font-weight: 700;
}}
[data-testid="stSidebarNav"] {{
    border-bottom: 1px solid rgba(56, 189, 248, 0.25);
}}
/* Sidebar content (Home's Data panel): light text on navy, ghost button. */
[data-testid="stSidebarUserContent"] h1,
[data-testid="stSidebarUserContent"] h2,
[data-testid="stSidebarUserContent"] h3 {{
    color: #ffffff !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}}
[data-testid="stSidebarUserContent"] p,
[data-testid="stSidebarUserContent"] span,
[data-testid="stSidebarUserContent"] strong {{
    color: rgba(224, 242, 254, 0.85) !important;
}}
[data-testid="stSidebarUserContent"] [data-testid="stCaptionContainer"] p {{
    color: rgba(186, 230, 253, 0.6) !important;
}}
[data-testid="stSidebarUserContent"] .stButton > button {{
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.55);
}}
[data-testid="stSidebarUserContent"] .stButton > button p {{
    color: #e0f2fe !important;
    font-weight: 600;
}}
[data-testid="stSidebarUserContent"] .stButton > button:hover {{
    background: rgba(56, 189, 248, 0.22);
    box-shadow: 0 0 16px -4px rgba(56, 189, 248, 0.7) !important;
}}

/* Dataframes read as cards too */
div[data-testid="stDataFrame"] {{
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 10px;
    overflow: hidden;
}}

hr {{
    border-color: {c["border"]} !important;
    margin: 1.4rem 0 !important;
}}

/* Team page special teams: the main "Power play %" / "Penalty kill %"
   labels bold and a bit bigger; the smaller "Season" label beside them
   keeps the normal metric label look. The label is a <label> element in
   Streamlit 1.65 (so not matched by the div[...stMetricLabel] rules above). */
div[class*="st-key-special_"] [data-testid="stMetricLabel"] p {{
    font-size: 1rem !important;
    font-weight: 700 !important;
}}
div[class*="st-key-special_"] div[class*="st-key-metric_secondary_"] [data-testid="stMetricLabel"] p {{
    font-size: 0.875rem !important;
    font-weight: 400 !important;
}}

/* Header season picker (segmented control, key _season_picker in
   dashboard/data.py): the selected season is a solid accent button, like
   the active view button on Standings, so it reads as clearly chosen. */
.st-key-_season_picker button {{
    font-weight: 600 !important;
}}
.st-key-_season_picker button[aria-checked="true"] {{
    background-color: {c["accent"]} !important;
    border-color: {c["accent"]} !important;
    color: #ffffff !important;
}}
.st-key-_season_picker button[aria-checked="true"] p {{
    color: #ffffff !important;
}}

/* Sidebar always open: pages start it expanded (initial_sidebar_state in
   st.set_page_config) and these hide the buttons that collapse/reopen it. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"] {{
    display: none !important;
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
