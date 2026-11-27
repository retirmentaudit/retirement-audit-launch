"""Paper canvas, navy type, and dark-on-light inputs (including iOS Safari)."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap');
html, body, [class*="css"] {
  font-family: Inter, "Segoe UI", sans-serif;
}
.stApp {
  background: #F7F5F0;
  color: #0B1F3A;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: #0B1F3A;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
  color: #F7F5F0 !important;
  -webkit-text-fill-color: #F7F5F0 !important;
}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] p,
label, .stRadio label, .stCheckbox label {
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
}
.hero {
  background: #0B1F3A;
  color: #F7F5F0;
  border-radius: 28px;
  padding: 36px 32px;
  margin-bottom: 18px;
}
.hero h1, .hero p, .hero li { color: #F7F5F0 !important; -webkit-text-fill-color: #F7F5F0 !important; }
.hero h1 {
  font-family: "Space Grotesk", Inter, sans-serif;
  font-size: 3.1rem;
  line-height: 1.02;
  margin: 0 0 8px 0;
}
.tagline { font-size: 1.35rem; margin: 0 0 8px 0; }
.alt-tag { color: #2BD9A0 !important; -webkit-text-fill-color: #2BD9A0 !important; font-weight: 600; }
.strip, .disclaimer, .fine-print {
  background: #ffffff;
  border: 1px solid #E4DFD4;
  border-left: 6px solid #FF6B5A;
  border-radius: 14px;
  padding: 14px 16px;
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
  font-size: 0.95rem;
  line-height: 1.45;
}
.rules {
  background: #E7FBF4;
  border: 1px solid #2BD9A0;
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
  color: #0B1F3A;
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
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
  caret-color: #0B1F3A !important;
  color-scheme: light;
}
input::placeholder, textarea::placeholder {
  color: #64748b !important;
  -webkit-text-fill-color: #64748b !important;
  opacity: 1 !important;
}
input:-webkit-autofill, textarea:-webkit-autofill {
  -webkit-text-fill-color: #0B1F3A !important;
  caret-color: #0B1F3A !important;
}
[data-baseweb="select"] > div {
  background-color: #ffffff !important;
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
}
[data-baseweb="select"] span,
[data-baseweb="select"] div {
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
}
div.stButton > button[kind="primary"],
div.stButton > button[data-testid="stBaseButton-primary"] {
  background: #0B1F3A !important;
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
  color: #0B1F3A !important;
  border: 1px solid #0B1F3A !important;
  border-radius: 12px !important;
}
div.stButton > button[kind="secondary"] *,
div.stButton > button[data-testid="stBaseButton-secondary"] * {
  color: #0B1F3A !important;
  -webkit-text-fill-color: #0B1F3A !important;
}
div[data-testid="stAlert"] * { color: #0B1F3A !important; -webkit-text-fill-color: #0B1F3A !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
  background: #fff1f0 !important;
  border: 1px solid #FF6B5A !important;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background: #eef7ff !important;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
  background: #E7FBF4 !important;
}
[data-testid="stToolbarActions"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] p {
  color: #F7F5F0 !important;
  -webkit-text-fill-color: #F7F5F0 !important;
}
div.stLinkButton > a,
div.stLinkButton > a *,
a[data-testid="stBaseLinkButton-primary"],
a[data-testid="stBaseLinkButton-primary"] *,
a[data-testid="stBaseLinkButton-primary"]:hover,
a[data-testid="stBaseLinkButton-primary"]:hover * {
  background-color: #0B1F3A !important;
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
</style>
"""
