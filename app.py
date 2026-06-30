"""
NDPR Redactor — Production SaaS
Blue & Gold | SQLite auth | Tiered subscriptions | Paystack billing | NDPA 2023
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from db import init_db
from pages.auth_page    import auth_page
from pages.dashboard    import dashboard_page
from pages.redact_page  import redact_page
from pages.preview_page import preview_page
from pages.audit_page   import audit_page
from pages.billing_page import billing_page
from pages.settings_page import settings_page
from pages.admin_page   import admin_page
from pages.about_page   import about_page
from db.usage_db        import get_usage
from config             import tier_config, TIERS

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Slit — Enterprise Data Safety",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Slit v2.0 — Enterprise Data Safety & Compliance Platform"},
)

# ── Database init ─────────────────────────────────────────────────────────────
init_db()

# ── Session state defaults ────────────────────────────────────────────────────
for _k, _v in {
    "user":           None,
    "page":           "Dashboard",
    "dark_mode":      True,
    "uploaded_files": {},
    "active_file":    None,
    "detected_cols":  {},
    "redact_cfg":     {},
    "processed_df":   None,
    "proc_stats":     {},
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS / Theme ───────────────────────────────────────────────────────────────
def _inject_css() -> None:
    dark   = st.session_state.dark_mode
    bg     = "#070d1b" if dark else "#f4f7ff"
    surf   = "#0f1e3d" if dark else "#ffffff"
    surf2  = "#162548" if dark else "#eef2fd"
    border = "#1e3560" if dark else "#cdd8f6"
    text   = "#e8edf8" if dark else "#0a1226"
    muted  = "#7a90b8" if dark else "#5a6e94"
    BLUE   = "#2563eb"
    BLUEH  = "#3b82f6"
    GOLD   = "#f0a500"
    GOLDH  = "#fbbf24"
    GOLDD  = "#c98900"

    st.markdown(f"""<style>
.stApp{{background:{bg};color:{text};font-family:"Inter","Segoe UI",system-ui,sans-serif}}
.main .block-container{{padding-top:1.3rem;max-width:1380px}}
[data-testid="stSidebar"]{{background:{surf};border-right:1px solid {border}}}
.stButton>button{{background:{GOLD};color:#0a1226;border:none;border-radius:7px;
  font-weight:700;font-size:0.87rem;padding:0.46rem 1.1rem;transition:all 0.15s ease}}
.stButton>button:hover{{background:{GOLDH};transform:translateY(-1px);
  box-shadow:0 4px 16px rgba(240,165,0,.35)}}
.stButton>button:active{{background:{GOLDD};transform:translateY(0)}}
.stTabs [data-baseweb="tab-list"]{{gap:2px;background:{surf};border-radius:10px;
  padding:4px;border:1px solid {border};margin-bottom:1rem}}
.stTabs [data-baseweb="tab"]{{border-radius:7px;color:{muted};font-weight:600;
  font-size:0.84rem;padding:0.42rem 0.95rem;transition:all 0.14s}}
.stTabs [aria-selected="true"]{{background:linear-gradient(135deg,{BLUE},{BLUEH}) !important;
  color:#fff !important;box-shadow:0 2px 8px rgba(37,99,235,.4) !important}}
.stTextInput input,.stTextArea textarea{{background:{surf2} !important;
  border-color:{border} !important;color:{text} !important;border-radius:7px !important}}
.stTextInput input:focus,.stTextArea textarea:focus{{border-color:{BLUE} !important;
  box-shadow:0 0 0 2px rgba(37,99,235,.2) !important}}
[data-testid="stMetric"]{{background:{surf};border:1px solid {border};border-radius:10px;padding:.75rem 1rem}}
[data-testid="stMetricValue"]{{color:{GOLD} !important;font-weight:800}}
[data-testid="stMetricLabel"]{{color:{muted} !important;font-size:.77rem;text-transform:uppercase;letter-spacing:.06em}}
[data-testid="stProgressBar"]>div{{background:{BLUE} !important}}
[data-testid="stFileUploaderDropzone"]{{background:{surf} !important;
  border:2px dashed {BLUE}88 !important;border-radius:12px !important}}
[data-testid="stFileUploaderDropzone"]:hover{{border-color:{GOLD} !important}}
.card{{background:{surf};border:1px solid {border};border-radius:12px;
  padding:1.2rem 1.4rem;margin-bottom:.9rem}}
.card-gold{{background:{surf};border:1px solid {GOLD}55;border-left:4px solid {GOLD};
  border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:.9rem}}
.card-blue{{background:{surf};border:1px solid {BLUE}55;border-left:4px solid {BLUE};
  border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:.9rem}}
.card-warn{{background:{surf};border-left:4px solid #f59e0b;border-radius:12px;
  padding:1rem 1.4rem;margin-bottom:.9rem}}
.badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.72rem;
  font-weight:700;letter-spacing:.03em;line-height:1.7}}
.badge-blue{{background:rgba(37,99,235,.15);color:{BLUEH};border:1px solid rgba(37,99,235,.3)}}
.badge-gold{{background:rgba(240,165,0,.15);color:{GOLD};border:1px solid rgba(240,165,0,.3)}}
.badge-green{{background:rgba(16,185,129,.15);color:#10b981;border:1px solid rgba(16,185,129,.3)}}
.badge-gray{{background:rgba(120,144,184,.12);color:{muted};border:1px solid rgba(120,144,184,.2)}}
.badge-red{{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.25)}}
.page-header{{background:linear-gradient(135deg,{surf} 0%,{surf2} 100%);
  border:1px solid {border};border-radius:14px;padding:1.3rem 1.7rem;
  margin-bottom:1.4rem;position:relative;overflow:hidden}}
.page-header::before{{content:"";position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,{BLUE},{GOLD})}}
.page-title{{font-size:1.5rem;font-weight:800;color:{text};margin:0;line-height:1.2}}
.page-sub{{color:{muted};font-size:.87rem;margin:.3rem 0 0}}
[data-testid="stDataFrame"]{{border-radius:10px;overflow:hidden}}
hr{{border-color:{border};margin:.7rem 0}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:{bg}}}
::-webkit-scrollbar-thumb{{background:{BLUE}66;border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:{GOLD}99}}
.stSelectbox [data-baseweb="select"]>div{{background:{surf2} !important;
  border-color:{border} !important;color:{text} !important}}
</style>""", unsafe_allow_html=True)

_inject_css()

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.user:
    auth_page()
    st.stop()

user = st.session_state.user
tier = user["tier"]
cfg  = tier_config(tier)
tcol = TIERS.get(tier, {}).get("badge_colour", "#6b7280")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo + user
    st.markdown(
        f"<div style='margin-bottom:.3rem'>"
        f"<span style='font-size:1.4rem'>🔒</span>"
        f"<span style='font-weight:900;font-size:1.15rem;margin-left:.4rem;letter-spacing:-0.02em;color:#f0a500'>Slit</span>"
        f"</div>"
        f"<div style='margin-bottom:.3rem'>"
        f"<span style='font-weight:600;font-size:.88rem'>{user['full_name']}</span><br>"
        f"<span style='font-size:.74rem;color:#7a90b8'>{user['email']}</span>"
        f"</div>"
        f"<span style='background:{tcol}22;color:{tcol};border:1px solid {tcol}44;"
        f"border-radius:20px;padding:2px 10px;font-size:.72rem;font-weight:700'>"
        f"{cfg['name']} Plan</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Theme toggle
    dark = st.session_state.dark_mode
    if st.button("🌙 Dark" if dark else "☀️ Light", use_container_width=True):
        st.session_state.dark_mode = not dark
        st.rerun()

    st.divider()

    # Usage mini-bar
    usage      = get_usage(user["id"])
    files_used = usage["files_processed"]
    files_max  = cfg["max_files_month"]
    st.markdown(
        f"<div style='font-size:.74rem;color:#7a90b8;margin-bottom:.2rem'>"
        f"📁 {files_used} / {'∞' if not files_max else files_max} files this month</div>",
        unsafe_allow_html=True,
    )
    if files_max:
        st.progress(min(files_used / files_max, 1.0))

    st.divider()

    # Navigation
    USER_PAGES = [
        "Dashboard", "Upload & Redact", "Preview & Process",
        "Audit Log", "Billing", "Settings", "About NDPR"
    ]
    NAV_ICONS = {
        "Dashboard":       "🏠",
        "Upload & Redact": "📤",
        "Preview & Process":"👁️",
        "Audit Log":       "📋",
        "Billing":         "💳",
        "Settings":        "⚙️",
        "About NDPR":      "🛡️",
        "Admin Panel":     "🔧",
    }
    pages = USER_PAGES[:]
    if user.get("role") == "admin":
        pages.append("Admin Panel")

    current = st.session_state.page
    for pg in pages:
        icon   = NAV_ICONS.get(pg, "•")
        active = pg == current
        style  = ("background:#f0a50022;color:#f0a500;border:1px solid #f0a50044;"
                  if active else "background:transparent;color:#7a90b8;border:1px solid transparent;")
        if st.button(
            f"{icon}  {pg}",
            key=f"nav_{pg}",
            use_container_width=True,
        ):
            if pg != current:
                st.session_state.page = pg
                st.rerun()

    st.divider()

    # File management
    if st.session_state.uploaded_files:
        st.markdown(
            "<span style='font-size:.75rem;font-weight:700;text-transform:uppercase;"
            "letter-spacing:.07em;color:#7a90b8'>Loaded Files</span>",
            unsafe_allow_html=True,
        )
        for fn in list(st.session_state.uploaded_files.keys()):
            fc1, fc2 = st.columns([5, 1])
            with fc1:
                is_active = fn == st.session_state.active_file
                lbl = ("▶ " if is_active else "  ") + fn[:20]
                if st.button(lbl, key=f"sb_fn_{fn}", use_container_width=True):
                    st.session_state.active_file = fn
                    df = st.session_state.uploaded_files[fn]["df"]
                    from pages.redact_page import _set_active
                    _set_active(fn, df)
                    st.rerun()
            with fc2:
                if st.button("✕", key=f"sb_rm_{fn}"):
                    del st.session_state.uploaded_files[fn]
                    rem = list(st.session_state.uploaded_files.keys())
                    st.session_state.active_file = rem[0] if rem else None
                    st.session_state.processed_df = None
                    if not rem:
                        st.session_state.redact_cfg = {}
                        st.session_state.detected_cols = {}
                    st.rerun()
        st.divider()

    if st.button("🚪 Sign Out", use_container_width=True):
        for k in ["user","uploaded_files","active_file","detected_cols",
                  "redact_cfg","processed_df","proc_stats","page"]:
            st.session_state[k] = None if k == "user" else ({} if k in
                ["uploaded_files","detected_cols","redact_cfg","proc_stats"] else
                ([] if k == "session_logs" else None))
        st.session_state.page = "Dashboard"
        st.rerun()

# ── Page router ───────────────────────────────────────────────────────────────
_PAGE_MAP = {
    "Dashboard":        dashboard_page,
    "Upload & Redact":  redact_page,
    "Preview & Process":preview_page,
    "Audit Log":        audit_page,
    "Billing":          billing_page,
    "Settings":         settings_page,
    "Admin Panel":      admin_page,
    "About NDPR":       about_page,
}

page_fn = _PAGE_MAP.get(st.session_state.page, dashboard_page)
page_fn()
