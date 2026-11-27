"""Paper canvas, navy type, and dark-on-light inputs (including iOS Safari)."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap');
html, body, [class*="css"] {
  font-family: Inter, "Segoe UI", sans-serif;
}
.stApp {
  background: #F6F5F2;
  color: #1C2430;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: #1C2430;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
  color: #F6F5F2 !important;
  -webkit-text-fill-color: #F6F5F2 !important;
}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] p,
label, .stRadio label, .stCheckbox label {
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
}
.hero {
  background: #1C2430;
  color: #F6F5F2;
  border-radius: 28px;
  padding: 36px 32px;
  margin-bottom: 18px;
}
.hero h1, .hero p, .hero li { color: #F6F5F2 !important; -webkit-text-fill-color: #F6F5F2 !important; }
.hero h1 {
  font-family: "Space Grotesk", Inter, sans-serif;
  font-size: 3.1rem;
  line-height: 1.02;
  margin: 0 0 8px 0;
}
.tagline { font-size: 1.35rem; margin: 0 0 8px 0; }
.alt-tag { color: #FF7A1A !important; -webkit-text-fill-color: #FF7A1A !important; font-weight: 600; }
.strip, .disclaimer, .fine-print {
  background: #ffffff;
  border: 1px solid #E4DFD4;
  border-left: 6px solid #FF7A1A;
  border-radius: 14px;
  padding: 14px 16px;
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
  font-size: 0.95rem;
  line-height: 1.45;
}
.rules {
  background: #FFF1E6;
  border: 1px solid #FF7A1A;
  border-radius: 14px;
  padding: 12px 16px;
  margin: 8px 0 14px 0;
}
.card {
  background: #ffffff;
  border: 1px solid #E4DFD4;
  border-radius: 18px;
  padding: 16px 18px;
  margin-bottom: 12px;
}
.big {
  font-family: "Space Grotesk", Inter, sans-serif;
  font-size: 2.2rem;
  font-weight: 700;
  color: #1C2430;
  margin: 0;
}
.mint { color: #14956C !important; -webkit-text-fill-color: #14956C !important; }
.coral { color: #C2412F !important; -webkit-text-fill-color: #C2412F !important; }
.chip {
  display: inline-block;
  margin: 0 8px 8px 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid #D9D3C7;
  font-size: 0.88rem;
}
.blur-target {
  filter: blur(7px);
  user-select: none;
  pointer-events: none;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stChatInput"] textarea,
textarea,
input[type="text"],
input[type="password"],
input[type="email"],
input[type="number"] {
  background-color: #ffffff !important;
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
  caret-color: #1C2430 !important;
  color-scheme: light;
}
input::placeholder, textarea::placeholder {
  color: #64748b !important;
  -webkit-text-fill-color: #64748b !important;
  opacity: 1 !important;
}
input:-webkit-autofill, textarea:-webkit-autofill {
  -webkit-text-fill-color: #1C2430 !important;
  caret-color: #1C2430 !important;
}
[data-baseweb="select"] > div {
  background-color: #ffffff !important;
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] div {
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
}
div.stButton > button[kind="primary"],
div.stButton > button[data-testid="stBaseButton-primary"] {
  background: #1C2430 !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
}
div.stButton > button[kind="primary"] *,
div.stButton > button[data-testid="stBaseButton-primary"] * {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
div.stButton > button[kind="secondary"],
div.stButton > button[data-testid="stBaseButton-secondary"] {
  background: #ffffff !important;
  color: #1C2430 !important;
  border: 1px solid #1C2430 !important;
  border-radius: 12px !important;
}
div.stButton > button[kind="secondary"] *,
div.stButton > button[data-testid="stBaseButton-secondary"] * {
  color: #1C2430 !important;
  -webkit-text-fill-color: #1C2430 !important;
}
div[data-testid="stAlert"] * { color: #1C2430 !important; -webkit-text-fill-color: #1C2430 !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
  background: #fff1f0 !important;
  border: 1px solid #FF7A1A !important;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background: #eef7ff !important;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
  background: #FFF1E6 !important;
}
[data-testid="stToolbarActions"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] p {
  color: #F6F5F2 !important;
  -webkit-text-fill-color: #F6F5F2 !important;
}
div.stLinkButton > a,
div.stLinkButton > a *,
a[data-testid="stBaseLinkButton-primary"],
a[data-testid="stBaseLinkButton-primary"] *,
a[data-testid="stBaseLinkButton-primary"]:hover,
a[data-testid="stBaseLinkButton-primary"]:hover * {
  background-color: #1C2430 !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
</style>
"""

THEME_CSS = THEME_CSS.replace(
    "</style>",
    """
.verdict { display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.82rem; font-weight:600; }
.v-expected { background:#E8F7EE; color:#17663A !important; -webkit-text-fill-color:#17663A !important; }
.v-verify { background:#EEF2F7; color:#334155 !important; -webkit-text-fill-color:#334155 !important; }
.v-optional { background:#FFF1E6; color:#9A4A00 !important; -webkit-text-fill-color:#9A4A00 !important; }
.v-ask { background:#FFF7D6; color:#7A5B00 !important; -webkit-text-fill-color:#7A5B00 !important; }
.v-over_limit, .v-above_presumed { background:#FDE8E8; color:#A61B1B !important; -webkit-text-fill-color:#A61B1B !important; }
.line { background:#fff; border:1px solid #E4DFD4; border-radius:14px; padding:12px 14px; margin-bottom:8px; }
.line .amt { float:right; font-family:"Space Grotesk", Inter, sans-serif; font-weight:700; }
[data-testid="stMarkdownContainer"] p.big { font-size: 2.1rem !important; line-height: 1.1; margin: 4px 0 !important; }
[data-testid="stMarkdownContainer"] p.big.coral { color:#C2410C !important; -webkit-text-fill-color:#C2410C !important; }
.lock { background:#fff; border:2px dashed #FF7A1A; border-radius:18px; padding:18px; margin:12px 0; }
</style>""",
)
