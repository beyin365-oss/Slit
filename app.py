"""
NDPR Data Redaction Tool
Blue & Gold Edition — Clean, professional, NDPA 2023 compliant.
Tabs: Upload & Redact | Preview | Audit Log | About NDPR
"""

import os
import sys
import uuid
import json
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from utils.detector import SensitiveDataDetector
from utils.redactor import DataRedactor
from utils.audit import AuditLogger, load_persisted_logs, hash_file
from utils.file_handler import read_file, write_file, file_info, MAX_FILE_SIZE_MB

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="NDPR Redaction Tool",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "NDPR Data Redaction Tool — NDPA 2023 Compliant"},
)

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
_DEFAULTS: dict = {
    "authenticated":    False,
    "dark_mode":        True,
    "session_id":       str(uuid.uuid4())[:8].upper(),
    # file state
    "uploaded_files":   {},        # name → {df, fmt, raw, info, hash}
    "active_file":      None,
    # detection & config
    "detected_cols":    {},
    "redact_cfg":       {},
    # processing results
    "processed_df":     None,
    "proc_stats":       {},
    # audit (in-session + persisted merge)
    "session_logs":     [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ══════════════════════════════════════════════════════════════════════════════
#  THEME & CSS
# ══════════════════════════════════════════════════════════════════════════════
def _inject_css() -> None:
    dark = st.session_state.dark_mode

    # Base palette
    bg        = "#070d1b" if dark else "#f4f7ff"
    surface   = "#0f1e3d" if dark else "#ffffff"
    surface2  = "#162548" if dark else "#eef2fd"
    border    = "#1e3560" if dark else "#cdd8f6"
    text      = "#e8edf8" if dark else "#0a1226"
    muted     = "#7a90b8" if dark else "#5a6e94"

    BLUE   = "#2563eb"
    BLUE_H = "#3b82f6"
    GOLD   = "#f0a500"
    GOLD_H = "#fbbf24"
    GOLD_D = "#c98900"

    st.markdown(f"""
<style>
/* ── Reset & base ── */
.stApp {{ background:{bg}; color:{text}; font-family:"Inter","Segoe UI",system-ui,sans-serif; }}
.main .block-container {{ padding-top:1.4rem; max-width:1380px; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background:{surface};
    border-right:1px solid {border};
}}

/* ── Primary button (gold) ── */
.stButton > button {{
    background:{GOLD};
    color:#0a1226;
    border:none;
    border-radius:7px;
    font-weight:700;
    font-size:0.88rem;
    letter-spacing:0.02em;
    padding:0.48rem 1.1rem;
    transition:all 0.15s ease;
}}
.stButton > button:hover {{
    background:{GOLD_H};
    transform:translateY(-1px);
    box-shadow:0 4px 16px rgba(240,165,0,0.35);
}}
.stButton > button:active {{
    background:{GOLD_D};
    transform:translateY(0);
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap:2px;
    background:{surface};
    border-radius:10px;
    padding:4px;
    border:1px solid {border};
    margin-bottom:1rem;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius:7px;
    color:{muted};
    font-weight:600;
    font-size:0.85rem;
    padding:0.45rem 1rem;
    transition:all 0.15s;
}}
.stTabs [aria-selected="true"] {{
    background:linear-gradient(135deg,{BLUE},{BLUE_H}) !important;
    color:#ffffff !important;
    box-shadow:0 2px 8px rgba(37,99,235,0.4) !important;
}}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"]>div {{
    background:{surface2} !important;
    border-color:{border} !important;
    color:{text} !important;
    border-radius:7px !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color:{BLUE} !important;
    box-shadow:0 0 0 2px rgba(37,99,235,0.2) !important;
}}

/* ── Metrics ── */
[data-testid="stMetric"] {{
    background:{surface};
    border:1px solid {border};
    border-radius:10px;
    padding:0.8rem 1rem;
}}
[data-testid="stMetricValue"] {{ color:{GOLD} !important; font-weight:800; }}
[data-testid="stMetricLabel"] {{ color:{muted} !important; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em; }}

/* ── Progress ── */
[data-testid="stProgressBar"]>div {{ background:{BLUE} !important; }}

/* ── File uploader ── */
[data-testid="stFileUploaderDropzone"] {{
    background:{surface} !important;
    border:2px dashed {BLUE}88 !important;
    border-radius:12px !important;
    transition:border-color 0.2s;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color:{GOLD} !important;
}}

/* ── Custom cards ── */
.card {{
    background:{surface};
    border:1px solid {border};
    border-radius:12px;
    padding:1.2rem 1.4rem;
    margin-bottom:0.9rem;
}}
.card-gold {{
    background:{surface};
    border:1px solid {GOLD}55;
    border-left:4px solid {GOLD};
    border-radius:12px;
    padding:1.1rem 1.4rem;
    margin-bottom:0.9rem;
}}
.card-blue {{
    background:{surface};
    border:1px solid {BLUE}55;
    border-left:4px solid {BLUE};
    border-radius:12px;
    padding:1.1rem 1.4rem;
    margin-bottom:0.9rem;
}}
.card-warn {{
    background:{surface};
    border-left:4px solid #f59e0b;
    border-radius:12px;
    padding:1rem 1.4rem;
    margin-bottom:0.9rem;
}}

/* ── Badges ── */
.badge {{
    display:inline-block;
    padding:2px 10px;
    border-radius:20px;
    font-size:0.72rem;
    font-weight:700;
    letter-spacing:0.03em;
    line-height:1.7;
}}
.badge-blue  {{ background:rgba(37,99,235,0.15); color:{BLUE_H}; border:1px solid rgba(37,99,235,0.3); }}
.badge-gold  {{ background:rgba(240,165,0,0.15); color:{GOLD};   border:1px solid rgba(240,165,0,0.3); }}
.badge-green {{ background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); }}
.badge-gray  {{ background:rgba(120,144,184,0.12); color:{muted}; border:1px solid rgba(120,144,184,0.2); }}
.badge-red   {{ background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.25); }}

/* ── Page header ── */
.page-header {{
    background:linear-gradient(135deg,{surface} 0%,{surface2} 100%);
    border:1px solid {border};
    border-radius:14px;
    padding:1.4rem 1.8rem;
    margin-bottom:1.4rem;
    position:relative;
    overflow:hidden;
}}
.page-header::before {{
    content:"";
    position:absolute;
    top:0;left:0;right:0;
    height:3px;
    background:linear-gradient(90deg,{BLUE},{GOLD});
}}
.page-title {{
    font-size:1.5rem;
    font-weight:800;
    color:{text};
    margin:0;
    line-height:1.2;
}}
.page-sub {{
    color:{muted};
    font-size:0.88rem;
    margin:0.3rem 0 0;
}}

/* ── App logo strip ── */
.logo-strip {{
    display:flex;
    align-items:center;
    gap:0.7rem;
    margin-bottom:0.5rem;
}}
.logo-icon {{
    font-size:1.6rem;
    line-height:1;
}}
.logo-text {{
    font-size:1rem;
    font-weight:800;
    color:{text};
    line-height:1.1;
}}
.logo-sub {{
    font-size:0.7rem;
    color:{muted};
    font-weight:400;
}}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {{ border-radius:10px; overflow:hidden; }}

/* ── Divider ── */
hr {{ border-color:{border}; margin:0.8rem 0; }}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label {{ color:{text}; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width:5px; height:5px; }}
::-webkit-scrollbar-track {{ background:{bg}; }}
::-webkit-scrollbar-thumb {{ background:{BLUE}66; border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:{GOLD}99; }}

/* ── Select ── */
[data-baseweb="select"] [data-baseweb="popover"] {{
    background:{surface} !important;
    border:1px solid {border} !important;
}}

/* ── Footer ── */
.footer {{
    text-align:center;
    color:{muted};
    font-size:0.75rem;
    padding:1.2rem 0 0.3rem;
    border-top:1px solid {border};
    margin-top:1.5rem;
    line-height:1.7;
}}

/* ── Highlight redacted ── */
.redacted-tag {{
    background:rgba(37,99,235,0.18);
    color:#93c5fd;
    border-radius:3px;
    padding:1px 5px;
    font-family:monospace;
    font-size:0.82em;
}}
</style>""", unsafe_allow_html=True)

_inject_css()

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & HELPERS
# ══════════════════════════════════════════════════════════════════════════════
ACCESS_CODE = os.environ.get("ACCESS_CODE", "NDPR2024")

METHODS = {
    "hash":         "SHA-256 Hash",
    "pseudonymize": "Pseudonymize",
    "mask":         "Smart Mask",
    "remove":       "Remove Column",
    "regex":        "Custom Regex",
}

METHOD_ICONS = {
    "hash": "🔒", "pseudonymize": "🎭", "mask": "🙈",
    "remove": "🗑️", "regex": "🔧",
}

DARK_BLUE  = "#0f2044"
GOLD       = "#f0a500"
BLUE_ACC   = "#2563eb"


def _badge(text: str, kind: str = "blue") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def _conf_badge(conf: float) -> str:
    pct = int(conf * 100)
    if conf >= 0.85:
        return _badge(f"✓ {pct}%", "green")
    elif conf >= 0.6:
        return _badge(f"~ {pct}%", "gold")
    return _badge(f"? {pct}%", "gray")


def _build_redact_cfg(detected: dict) -> None:
    """Populate st.session_state.redact_cfg from detection results."""
    cfg = st.session_state.redact_cfg
    for col, info in detected.items():
        if col not in cfg:
            cfg[col] = {
                "enabled":           True,
                "method":            "mask",
                "field_type":        info["type"],
                "regex_pattern":     "",
                "regex_replacement": "[REDACTED]",
            }


def _all_logs() -> list[dict]:
    """Merge session logs with persisted logs (dedup by audit_id)."""
    session_ids = {e["audit_id"] for e in st.session_state.session_logs}
    persisted = [e for e in load_persisted_logs() if e["audit_id"] not in session_ids]
    return st.session_state.session_logs + persisted


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH GATE
# ══════════════════════════════════════════════════════════════════════════════
def _auth_gate() -> bool:
    if st.session_state.authenticated:
        return True

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align:center'>"
            f"<div style='font-size:3.5rem'>🔐</div>"
            f"<p style='font-size:1.6rem;font-weight:800;color:{GOLD};margin:0.2rem 0'>NDPR Redaction Tool</p>"
            "<p style='color:#7a90b8;font-size:0.9rem;margin-bottom:1.5rem'>Enter your access code to continue</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.form("auth_form", clear_on_submit=True):
            code = st.text_input("Access Code", type="password",
                                 placeholder="Access code…", label_visibility="collapsed")
            submitted = st.form_submit_button("Unlock →", use_container_width=True)
        if submitted:
            if code == ACCESS_CODE:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect access code.")
        st.markdown(
            "<p style='text-align:center;color:#4a5568;font-size:0.78rem;margin-top:0.6rem'>"
            "Contact your administrator for the access code."
            "</p>",
            unsafe_allow_html=True,
        )
    return False


if not _auth_gate():
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        f"<div class='logo-strip'>"
        f"<span class='logo-icon'>🔐</span>"
        f"<div><div class='logo-text'>NDPR Redaction</div>"
        f"<div class='logo-sub'>Session · {st.session_state.session_id}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Theme toggle
    dark = st.session_state.dark_mode
    if st.button(("🌙 Dark Mode" if dark else "☀️ Light Mode"), use_container_width=True):
        st.session_state.dark_mode = not dark
        st.rerun()

    st.divider()
    st.markdown("**Loaded Files**", )

    if not st.session_state.uploaded_files:
        st.caption("No files yet — upload in Upload & Redact.")
    else:
        for fname, fd in list(st.session_state.uploaded_files.items()):
            is_active = fname == st.session_state.active_file
            rc, xc = st.columns([5, 1])
            with rc:
                label = ("▶ " if is_active else "   ") + fname[:22]
                if st.button(label, key=f"sb_sel_{fname}", use_container_width=True):
                    _switch_file(fname) if False else None  # handled inline
                    st.session_state.active_file = fname
                    df = fd["df"]
                    det = SensitiveDataDetector().detect(df)
                    st.session_state.detected_cols = det
                    _build_redact_cfg(det)
                    st.session_state.processed_df = None
                    st.session_state.proc_stats = {}
                    st.rerun()
            with xc:
                if st.button("✕", key=f"sb_del_{fname}"):
                    del st.session_state.uploaded_files[fname]
                    if st.session_state.active_file == fname:
                        rem = list(st.session_state.uploaded_files.keys())
                        st.session_state.active_file = rem[0] if rem else None
                        st.session_state.processed_df = None
                        st.session_state.proc_stats = {}
                        st.session_state.detected_cols = {}
                        st.session_state.redact_cfg = {}
                    st.rerun()

    st.divider()

    # Saved templates
    st.markdown("**Templates**")
    if "templates" not in st.session_state:
        st.session_state.templates = {}

    if st.session_state.templates:
        tpl = st.selectbox("Load", ["— select —"] + list(st.session_state.templates.keys()),
                           label_visibility="collapsed")
        c1, c2 = st.columns(2)
        if c1.button("Apply", use_container_width=True) and tpl != "— select —":
            for col, c in st.session_state.templates[tpl].items():
                if col in st.session_state.redact_cfg:
                    st.session_state.redact_cfg[col].update(c)
            st.success("Applied!")
        if c2.button("Delete", use_container_width=True) and tpl != "— select —":
            del st.session_state.templates[tpl]
            st.rerun()
    else:
        st.caption("No templates saved.")

    st.divider()
    if st.button("🔒 Lock", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_main, tab_preview, tab_audit, tab_about = st.tabs([
    "📤 Upload & Redact",
    "👁️ Preview & Process",
    "📋 Audit Log",
    "🛡️ About NDPR",
])

# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 1 — UPLOAD & REDACT
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_main:
    # ── Header ──
    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Upload & Redact</p>"
        "<p class='page-sub'>Upload your data file, review auto-detected PII columns, and configure redaction methods.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── File Upload ──
    uploaded = st.file_uploader(
        "Drop CSV, Excel, or JSON files here",
        type=["csv", "xlsx", "xls", "json"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.uploaded_files:
                continue
            raw = f.read()
            if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(
                    f"**{f.name}** exceeds {MAX_FILE_SIZE_MB} MB "
                    f"({len(raw)/(1024*1024):.1f} MB). Please upload a smaller file."
                )
                continue
            with st.spinner(f"Parsing {f.name}…"):
                try:
                    df, fmt = read_file(raw, f.name)
                    info = file_info(df, f.name, raw)
                    fhash = hash_file(raw)
                    st.session_state.uploaded_files[f.name] = {
                        "df": df, "fmt": fmt, "raw": raw, "info": info, "hash": fhash
                    }
                    if not st.session_state.active_file:
                        st.session_state.active_file = f.name
                        det = SensitiveDataDetector().detect(df)
                        st.session_state.detected_cols = det
                        _build_redact_cfg(det)
                    st.success(f"✓ **{f.name}** — {info['rows']:,} rows × {info['columns']} columns")
                except ValueError as e:
                    st.error(f"**{f.name}**: {e}")

    # ── Active file selector ──
    if not st.session_state.uploaded_files:
        st.markdown(
            "<div class='card' style='text-align:center;padding:3rem'>"
            "<div style='font-size:3rem;margin-bottom:0.5rem'>📂</div>"
            f"<p style='font-weight:600'>No file loaded</p>"
            f"<p style='color:#7a90b8;font-size:0.85rem'>Supports CSV, Excel (.xlsx/.xls), JSON · max {MAX_FILE_SIZE_MB} MB</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    if len(st.session_state.uploaded_files) > 1:
        choices = list(st.session_state.uploaded_files.keys())
        idx = choices.index(st.session_state.active_file) if st.session_state.active_file in choices else 0
        chosen = st.selectbox("Active file", choices, index=idx)
        if chosen != st.session_state.active_file:
            st.session_state.active_file = chosen
            df = st.session_state.uploaded_files[chosen]["df"]
            det = SensitiveDataDetector().detect(df)
            st.session_state.detected_cols = det
            _build_redact_cfg(det)
            st.session_state.processed_df = None
            st.session_state.proc_stats = {}
            st.rerun()

    fname   = st.session_state.active_file
    fd      = st.session_state.uploaded_files[fname]
    df      = fd["df"]
    info    = fd["info"]
    cfg     = st.session_state.redact_cfg
    det     = st.session_state.detected_cols

    # ── File Info metrics ──
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Rows", f"{info['rows']:,}")
    mc2.metric("Columns", info["columns"])
    mc3.metric("Format", info["format"])
    mc4.metric("Size", info["size"])
    mc5.metric("Detected PII", len(det))

    # File hash display
    with st.expander("🔑 File Integrity Hash (SHA-256)", expanded=False):
        st.code(fd["hash"], language=None)
        st.caption("Record this hash to verify the original file was not altered before redaction.")

    st.divider()

    # ── Detection + Config controls ──
    hdr_c1, hdr_c2, hdr_c3, hdr_c4 = st.columns([4, 1, 1, 1])
    with hdr_c1:
        n_enabled = sum(1 for c in cfg.values() if c.get("enabled"))
        st.markdown(
            f"<div class='card-blue' style='padding:0.7rem 1.1rem;margin:0'>"
            f"<b>🔍 {len(det)} PII column(s) auto-detected</b> &nbsp;·&nbsp; "
            f"<b>{n_enabled}</b> enabled for redaction"
            f"</div>",
            unsafe_allow_html=True,
        )
    with hdr_c2:
        if st.button("🔍 Re-detect", use_container_width=True):
            det = SensitiveDataDetector().detect(df)
            st.session_state.detected_cols = det
            _build_redact_cfg(det)
            st.rerun()
    with hdr_c3:
        if st.button("↩ Reset All", use_container_width=True):
            st.session_state.redact_cfg = {}
            det = SensitiveDataDetector().detect(df)
            st.session_state.detected_cols = det
            _build_redact_cfg(det)
            st.rerun()
    with hdr_c4:
        if st.button("✅ Select All", use_container_width=True):
            for col in cfg:
                cfg[col]["enabled"] = True
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Global method override ──
    with st.expander("🌐 Global Override — set one method for all enabled columns"):
        ga, gb = st.columns([3, 1])
        with ga:
            g_method = st.selectbox("Method", list(METHODS.keys()),
                                    format_func=lambda x: f"{METHOD_ICONS[x]} {METHODS[x]}",
                                    key="global_override_method", label_visibility="collapsed")
        with gb:
            if st.button("Apply to All", use_container_width=True, key="apply_override"):
                for col in cfg:
                    if cfg[col].get("enabled"):
                        cfg[col]["method"] = g_method
                st.rerun()

    # ── Add custom column ──
    with st.expander("➕ Add column manually"):
        non_cfg = [c for c in df.columns if c not in cfg]
        if non_cfg:
            ca, cb = st.columns([4, 1])
            with ca:
                new_col = st.selectbox("Column", non_cfg, label_visibility="collapsed")
            with cb:
                if st.button("Add", use_container_width=True):
                    cfg[new_col] = {
                        "enabled": True, "method": "mask", "field_type": "generic",
                        "regex_pattern": "", "regex_replacement": "[REDACTED]",
                    }
                    st.rerun()
        else:
            st.success("All columns are already in the configuration.")

    # ── Save template ──
    with st.expander("💾 Save current config as template"):
        ta, tb = st.columns([4, 1])
        with ta:
            tpl_name = st.text_input("Template name", placeholder="e.g. Fintech KYC Standard",
                                     label_visibility="collapsed")
        with tb:
            if st.button("Save", use_container_width=True):
                if tpl_name.strip():
                    st.session_state.templates[tpl_name.strip()] = {
                        col: dict(c) for col, c in cfg.items()
                    }
                    st.success(f"Saved '{tpl_name.strip()}'")
                else:
                    st.warning("Enter a name first.")

    st.divider()

    # ── Column configuration table ──
    if not cfg:
        st.markdown(
            "<div class='card' style='text-align:center;padding:2rem'>"
            "<p style='color:#7a90b8'>No columns configured.<br>Use 'Add column manually' above.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Column headers
        h = st.columns([0.35, 2.2, 2.0, 2.4, 1.4, 0.8])
        for hcol, label in zip(h, ["", "Column", "Detected Type", "Method", "Confidence", "Remove"]):
            hcol.markdown(f"<span style='font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#7a90b8'>{label}</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:4px 0 8px'>", unsafe_allow_html=True)

        for col in list(cfg.keys()):
            c_cfg = cfg[col]
            det_info = det.get(col, {})
            confidence = det_info.get("confidence", 0)
            type_label = det_info.get("label", "Custom / Manual")
            source = det_info.get("source", "manual")

            row = st.columns([0.35, 2.2, 2.0, 2.4, 1.4, 0.8])

            # Enable checkbox
            with row[0]:
                enabled = st.checkbox("##en", value=c_cfg.get("enabled", True),
                                      key=f"en_{col}", label_visibility="collapsed")
                c_cfg["enabled"] = enabled

            # Column name
            with row[1]:
                src_icon = "📌" if "name" in source else "🔍"
                st.markdown(
                    f"`{col}`&nbsp;&nbsp;"
                    f"<span style='font-size:0.7rem;color:#7a90b8'>{src_icon}</span>",
                    unsafe_allow_html=True
                )

            # Detected type
            with row[2]:
                st.markdown(
                    f"<span style='font-size:0.84rem'>{type_label}</span>",
                    unsafe_allow_html=True
                )

            # Method selector
            with row[3]:
                current_method = c_cfg.get("method", "mask")
                chosen = st.selectbox(
                    "##m", list(METHODS.keys()),
                    format_func=lambda x: f"{METHOD_ICONS[x]} {METHODS[x]}",
                    index=list(METHODS.keys()).index(current_method) if current_method in METHODS else 0,
                    key=f"mth_{col}", label_visibility="collapsed",
                )
                c_cfg["method"] = chosen
                if chosen == "regex":
                    c_cfg["regex_pattern"] = st.text_input(
                        "Pattern", value=c_cfg.get("regex_pattern", ""),
                        key=f"rgxp_{col}", placeholder=r"e.g. \d{10}"
                    )
                    c_cfg["regex_replacement"] = st.text_input(
                        "Replacement", value=c_cfg.get("regex_replacement", "[REDACTED]"),
                        key=f"rgxr_{col}"
                    )

            # Confidence badge
            with row[4]:
                if confidence:
                    st.markdown(_conf_badge(confidence), unsafe_allow_html=True)
                else:
                    st.markdown(_badge("manual", "gray"), unsafe_allow_html=True)

            # Remove
            with row[5]:
                if st.button("✕", key=f"rm_{col}"):
                    del st.session_state.redact_cfg[col]
                    st.rerun()

            st.markdown("<hr style='margin:3px 0'>", unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 2 — PREVIEW & PROCESS
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_preview:
    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Preview & Process</p>"
        "<p class='page-sub'>Side-by-side before/after preview (first 50 rows), then process the full dataset.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.active_file:
        st.info("Upload a file in the Upload & Redact tab first.")
        st.stop()

    fname  = st.session_state.active_file
    df_orig = st.session_state.uploaded_files[fname]["df"]
    cfg    = st.session_state.redact_cfg
    enabled_cols = [c for c, v in cfg.items() if v.get("enabled") and c in df_orig.columns]

    if not enabled_cols:
        st.warning("No columns enabled for redaction. Configure in Upload & Redact.")
        st.stop()

    # Preview generation
    PREVIEW_ROWS = 50
    df_prev = df_orig.head(PREVIEW_ROWS).copy()
    with st.spinner("Building preview…"):
        df_prev_redacted, _ = DataRedactor().redact(df_prev.copy(), cfg)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"**Original** &nbsp;{_badge('BEFORE', 'gray')}", unsafe_allow_html=True)
        st.dataframe(df_prev, use_container_width=True, height=380)
    with col_r:
        st.markdown(f"**Redacted** &nbsp;{_badge('AFTER', 'blue')}", unsafe_allow_html=True)

        def _highlight_changed(row):
            styles = []
            for col in row.index:
                if col in enabled_cols and col in df_prev_redacted.columns:
                    orig = str(df_prev.at[row.name, col]) if row.name in df_prev.index else ""
                    new  = str(df_prev_redacted.at[row.name, col]) if row.name in df_prev_redacted.index else ""
                    styles.append("background-color:rgba(37,99,235,0.18);color:#93c5fd" if orig != new else "")
                else:
                    styles.append("")
            return styles

        try:
            styled = df_prev_redacted.head(PREVIEW_ROWS).style.apply(_highlight_changed, axis=1)
            st.dataframe(styled, use_container_width=True, height=380)
        except Exception:
            st.dataframe(df_prev_redacted.head(PREVIEW_ROWS), use_container_width=True, height=380)

    # What will be redacted
    removed_cols = [c for c, v in cfg.items() if v.get("enabled") and v.get("method") == "remove" and c in df_orig.columns]
    if removed_cols:
        st.markdown(
            f"<div class='card-warn'>⚠️ <b>Columns to be removed entirely:</b> "
            + ", ".join(f"<code>{c}</code>" for c in removed_cols)
            + "</div>",
            unsafe_allow_html=True,
        )

    tags = " ".join(
        _badge(f"{c} · {METHOD_ICONS.get(cfg[c]['method'], '')} {METHODS.get(cfg[c]['method'], '')}", "blue")
        for c in enabled_cols if c in cfg
    )
    st.markdown(f"<div style='margin:0.4rem 0'>{tags}</div>", unsafe_allow_html=True)

    st.divider()

    # ── Process ──
    st.markdown("### ⚡ Process Full Dataset")

    info = st.session_state.uploaded_files[fname]["info"]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Total Rows", f"{len(df_orig):,}")
    p2.metric("Columns to Redact", len(enabled_cols))
    p3.metric("File Size", info["size"])
    p4.metric("Format", info["format"])

    user_note = st.text_area("Audit note (optional)",
        placeholder="e.g. Pre-production QA dataset — NDPA compliant anonymisation",
        height=64)

    already_done = st.session_state.processed_df is not None
    btn_label = "🔄 Re-process" if already_done else "⚡ Redact & Process"

    if already_done:
        st.markdown(
            "<div class='card-gold'>✅ <b>Already processed.</b> Scroll to Download in Audit Log tab or re-process below.</div>",
            unsafe_allow_html=True,
        )

    if st.button(btn_label, use_container_width=True):
        pbar  = st.progress(0, text="Starting…")
        statbox = st.empty()
        try:
            n_rows  = len(df_orig)
            CHUNK   = 5000
            redactor = DataRedactor()
            chunks  = []
            final_stats: dict = {}

            if n_rows == 0:
                # Handle empty dataset gracefully
                df_out = df_orig.copy()
                pbar.progress(1.0, text="Complete!")
                statbox.warning("⚠️ The file has 0 data rows. An empty redacted file will be produced.")
            else:
                n_chunks = max(1, (n_rows + CHUNK - 1) // CHUNK)
                for i, start in enumerate(range(0, n_rows, CHUNK)):
                    chunk = df_orig.iloc[start:start + CHUNK].copy()
                    proc_chunk, chunk_stats = redactor.redact(chunk, cfg)
                    chunks.append(proc_chunk)
                    for col, s in chunk_stats.items():
                        if col not in final_stats:
                            final_stats[col] = {**s, "count": 0}
                        final_stats[col]["count"] += s.get("count", 0)
                    pct = (i + 1) / n_chunks
                    done = start + len(chunk)
                    pbar.progress(pct, text=f"Processing… {int(pct*100)}% ({done:,}/{n_rows:,} rows)")

                df_out = pd.concat(chunks, ignore_index=True)
            pbar.progress(1.0, text="Complete!")
            statbox.success("✅ Redaction complete!")

            st.session_state.processed_df = df_out
            st.session_state.proc_stats   = final_stats

            # Audit entry
            auditor = AuditLogger()
            entry   = auditor.create_entry(
                session_id=st.session_state.session_id,
                original_filename=fname,
                file_format=st.session_state.uploaded_files[fname]["fmt"],
                row_count=n_rows,
                column_count=len(df_orig.columns),
                redacted_columns={c: cfg[c] for c in enabled_cols if c in cfg},
                stats=final_stats,
                file_hash=st.session_state.uploaded_files[fname]["hash"],
                user_note=user_note,
            )
            st.session_state.session_logs.append(entry)

            # Stats
            st.markdown("#### Redaction Summary")
            total_vals = sum(s["count"] for s in final_stats.values())
            s_cols = st.columns(min(len(final_stats), 5))
            for i, (col, s) in enumerate(final_stats.items()):
                with s_cols[i % 5]:
                    st.metric(
                        col[:18],
                        f"{s['count']:,}",
                        help=f"Method: {s['method']} | Type: {s['field_type']}"
                    )

            st.markdown(
                f"<div class='card-gold'>"
                f"🏆 <b>{total_vals:,} values</b> redacted across <b>{len(final_stats)}</b> "
                f"column(s) in <b>{n_rows:,}</b> rows. "
                f"Audit ID: <code>{entry['audit_id']}</code>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Download
            st.markdown("#### ⬇️ Download Redacted File")
            fmt = st.session_state.uploaded_files[fname]["fmt"]
            out_bytes, mime, out_name = write_file(df_out, fmt, fname)
            dc1, dc2 = st.columns(2)
            with dc1:
                st.download_button(
                    f"⬇️ Download ({fmt.upper()})",
                    data=out_bytes, file_name=out_name, mime=mime,
                    use_container_width=True
                )
            with dc2:
                if fmt != "csv":
                    csv_b, _, csv_n = write_file(df_out, "csv", fname)
                    st.download_button(
                        "⬇️ Download (CSV)",
                        data=csv_b, file_name=csv_n, mime="text/csv",
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"Processing error: {e}")
            raise

    # Download if already processed
    elif already_done and st.session_state.processed_df is not None:
        st.markdown("#### ⬇️ Download Redacted File")
        fmt = st.session_state.uploaded_files[fname]["fmt"]
        df_out = st.session_state.processed_df
        out_bytes, mime, out_name = write_file(df_out, fmt, fname)
        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button(f"⬇️ Download ({fmt.upper()})",
                data=out_bytes, file_name=out_name, mime=mime, use_container_width=True)
        with dc2:
            if fmt != "csv":
                csv_b, _, csv_n = write_file(df_out, "csv", fname)
                st.download_button("⬇️ Download (CSV)",
                    data=csv_b, file_name=csv_n, mime="text/csv", use_container_width=True)

# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 3 — AUDIT LOG
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Audit Log</p>"
        "<p class='page-sub'>All redaction events — searchable, filterable, and exportable. Persisted across sessions.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    all_logs = _all_logs()

    if not all_logs:
        st.markdown(
            "<div class='card' style='text-align:center;padding:3rem'>"
            "<div style='font-size:2.5rem'>📋</div>"
            "<p style='font-weight:600;margin:0.5rem 0'>No audit entries yet</p>"
            "<p style='color:#7a90b8;font-size:0.85rem'>Process a file to create your first audit entry.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # ── Summary metrics ──
        total_rows = sum(e.get("rows_processed", 0) for e in all_logs)
        total_vals = sum(e.get("values_redacted_total", 0) for e in all_logs)
        lm1, lm2, lm3, lm4 = st.columns(4)
        lm1.metric("Total Entries", len(all_logs))
        lm2.metric("Files Processed", len(set(e["original_filename"] for e in all_logs)))
        lm3.metric("Rows Processed", f"{total_rows:,}")
        lm4.metric("Values Redacted", f"{total_vals:,}")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Search & Filter ──
        sf1, sf2, sf3 = st.columns([3, 2, 1])
        with sf1:
            search_q = st.text_input("🔍 Search", placeholder="filename, audit ID, note…",
                                     label_visibility="collapsed")
        with sf2:
            all_fmts = sorted(set(e.get("file_format", "") for e in all_logs))
            fmt_filter = st.multiselect("Format", all_fmts, label_visibility="collapsed",
                                        placeholder="Filter by format…")
        with sf3:
            if st.button("Clear Filters", use_container_width=True):
                st.rerun()

        # Apply filters
        filtered = all_logs
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [
                e for e in filtered
                if q in e.get("original_filename", "").lower()
                or q in e.get("audit_id", "").lower()
                or q in e.get("user_note", "").lower()
                or q in e.get("redaction_summary", "").lower()
                or q in e.get("session_id", "").lower()
            ]
        if fmt_filter:
            filtered = [e for e in filtered if e.get("file_format", "") in fmt_filter]

        st.caption(f"Showing {len(filtered)} of {len(all_logs)} entries")

        if filtered:
            display_cols = [
                "audit_id", "timestamp", "original_filename", "file_format",
                "rows_processed", "columns_redacted", "values_redacted_total",
                "ndpr_compliance", "user_note",
            ]
            df_log = pd.DataFrame(filtered)
            show_cols = [c for c in display_cols if c in df_log.columns]
            st.dataframe(df_log[show_cols], use_container_width=True, hide_index=True, height=320)

            # Expandable detail
            with st.expander("🔎 Detailed view (select entry)"):
                entry_ids = [e["audit_id"] for e in filtered]
                selected_id = st.selectbox("Entry", entry_ids, label_visibility="collapsed")
                entry = next((e for e in filtered if e["audit_id"] == selected_id), None)
                if entry:
                    detail_rows = [
                        ("Audit ID",          entry.get("audit_id", "")),
                        ("Timestamp",         entry.get("timestamp", "")),
                        ("Session",           entry.get("session_id", "")),
                        ("File",              entry.get("original_filename", "")),
                        ("Format",            entry.get("file_format", "")),
                        ("Rows Processed",    f"{entry.get('rows_processed', 0):,}"),
                        ("Columns Total",     str(entry.get("columns_total", ""))),
                        ("Columns Redacted",  str(entry.get("columns_redacted", ""))),
                        ("Values Redacted",   f"{entry.get('values_redacted_total', 0):,}"),
                        ("SHA-256 (file)",    entry.get("file_sha256", "—")),
                        ("NDPR Note",         entry.get("ndpr_compliance", "")),
                        ("User Note",         entry.get("user_note", "") or "—"),
                    ]
                    for k, v in detail_rows:
                        ca, cb = st.columns([2, 5])
                        ca.markdown(f"**{k}**")
                        cb.markdown(f"`{v}`" if len(v) > 40 else v)
                    st.markdown("**Redaction Summary:**")
                    for part in entry.get("redaction_summary", "").split(" | "):
                        st.markdown(f"- {part}")

        st.divider()

        # ── Export ──
        st.markdown("#### Export All Logs")
        ex1, ex2, ex3 = st.columns(3)
        auditor = AuditLogger()

        with ex1:
            # Export filtered
            csv_bytes = auditor.to_csv_bytes(filtered)
            st.download_button(
                "📊 Export Filtered (CSV)",
                data=csv_bytes,
                file_name=f"ndpr_audit_filtered_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex2:
            # Export ALL
            csv_all = auditor.to_csv_bytes(all_logs)
            st.download_button(
                "📊 Export All Logs (CSV)",
                data=csv_all,
                file_name=f"ndpr_audit_all_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex3:
            try:
                pdf_bytes = auditor.to_pdf_bytes(filtered, st.session_state.session_id)
                st.download_button(
                    "📑 Compliance Report (PDF)",
                    data=pdf_bytes,
                    file_name=f"ndpr_report_{st.session_state.session_id}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.caption(f"PDF unavailable: {e}")

        # Clear session logs only
        st.divider()
        if st.button("🗑️ Clear Session Logs", help="Removes in-session entries only. Persisted JSON is unchanged."):
            st.session_state.session_logs = []
            st.rerun()

# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TAB 4 — ABOUT NDPR
# ╚══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>About NDPR & NDPA 2023</p>"
        "<p class='page-sub'>Understanding Nigerian data protection law and how this tool supports compliance.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown(
            """<div class="card-gold">
            <h4 style="margin:0 0 0.5rem">🇳🇬 Nigeria Data Protection Act (NDPA) 2023</h4>
            <p style="line-height:1.8;margin:0">
            The <b>Nigeria Data Protection Act 2023</b> (signed June 2023) is Nigeria's
            comprehensive data protection law, replacing the 2019 NDPR. It establishes a
            statutory <b>Nigeria Data Protection Commission (NDPC)</b>, provides rights for
            data subjects, and imposes obligations on data controllers and processors.
            </p>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            """<div class="card">
            <h4 style="margin:0 0 0.7rem">📌 Key NDPA 2023 Principles</h4>
            <ul style="line-height:2.1;margin:0;padding-left:1.2rem">
              <li><b>Lawfulness, fairness and transparency</b> — process data only with a legal basis</li>
              <li><b>Purpose limitation</b> — collect data only for specified, explicit, legitimate purposes</li>
              <li><b>Data minimisation</b> — limit data to what is strictly necessary</li>
              <li><b>Accuracy</b> — keep personal data accurate and up to date</li>
              <li><b>Storage limitation</b> — do not retain data longer than necessary</li>
              <li><b>Integrity and confidentiality</b> — apply appropriate security measures</li>
              <li><b>Accountability</b> — demonstrate compliance with all principles</li>
            </ul>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            """<div class="card">
            <h4 style="margin:0 0 0.7rem">🔐 How Redaction Supports Compliance</h4>
            <table style="width:100%;border-collapse:collapse;font-size:0.88rem">
              <tr style="border-bottom:1px solid #1e3560">
                <th style="text-align:left;padding:6px 4px">Technique</th>
                <th style="text-align:left;padding:6px 4px">NDPA Principle</th>
                <th style="text-align:left;padding:6px 4px">Use case</th>
              </tr>
              <tr>
                <td style="padding:6px 4px"><b>SHA-256 Hash</b></td>
                <td style="padding:6px 4px">Data minimisation</td>
                <td style="padding:6px 4px">Irreversible anonymisation</td>
              </tr>
              <tr>
                <td style="padding:6px 4px"><b>Pseudonymise</b></td>
                <td style="padding:6px 4px">Storage limitation</td>
                <td style="padding:6px 4px">Safe test environments</td>
              </tr>
              <tr>
                <td style="padding:6px 4px"><b>Mask</b></td>
                <td style="padding:6px 4px">Confidentiality</td>
                <td style="padding:6px 4px">Display redaction in UIs</td>
              </tr>
              <tr>
                <td style="padding:6px 4px"><b>Remove</b></td>
                <td style="padding:6px 4px">Purpose limitation</td>
                <td style="padding:6px 4px">Strip fields not needed downstream</td>
              </tr>
            </table>
            </div>""",
            unsafe_allow_html=True,
        )

    with col_right:
        st.markdown(
            """<div class="card">
            <h4 style="margin:0 0 0.6rem">⚠️ PII Types Detected</h4>
            <ul style="line-height:2;margin:0;padding-left:1.2rem;font-size:0.88rem">
              <li>📞 Phone numbers (Nigerian &amp; international)</li>
              <li>📧 Email addresses</li>
              <li>👤 Full names &amp; surnames</li>
              <li>🏠 Physical addresses</li>
              <li>🏦 Bank account numbers (NUBAN)</li>
              <li>🪪 BVN (Bank Verification Number)</li>
              <li>🪪 NIN (National Identification Number)</li>
              <li>💳 Credit / debit card numbers</li>
              <li>🌐 IP addresses (IPv4 &amp; IPv6)</li>
              <li>📅 Dates of birth</li>
              <li>🔑 Passwords &amp; secret tokens</li>
              <li>🏛️ Bank details (IBAN, SWIFT, sort codes)</li>
            </ul>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            """<div class="card-blue">
            <h4 style="margin:0 0 0.6rem">🛡️ Compliance Statement</h4>
            <p style="font-size:0.85rem;line-height:1.75;margin:0;color:#7a90b8">
            This tool supports <b style="color:#e8edf8">data minimisation</b> and
            <b style="color:#e8edf8">pseudonymisation</b> principles under the
            <b style="color:#e8edf8">Nigeria Data Protection Act (NDPA) 2023</b>.
            All processing is performed <b style="color:#e8edf8">locally</b> —
            no personal data is transmitted to external services.
            <br><br>
            For production deployments handling highly sensitive personal data,
            deploy this tool on a private, access-controlled server and obtain
            appropriate legal and privacy counsel.
            </p>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""<div class="card">
            <h4 style="margin:0 0 0.6rem">⚙️ Tool Information</h4>
            <table style="font-size:0.85rem;width:100%">
              <tr><td><b>Version</b></td><td>1.0</td></tr>
              <tr><td><b>Python</b></td><td>3.13+</td></tr>
              <tr><td><b>Framework</b></td><td>Streamlit 1.58</td></tr>
              <tr><td><b>Max file size</b></td><td>{MAX_FILE_SIZE_MB} MB</td></tr>
              <tr><td><b>Supported formats</b></td><td>CSV, XLSX, XLS, JSON</td></tr>
              <tr><td><b>Audit persistence</b></td><td>audit_logs.json</td></tr>
              <tr><td><b>Hash algorithm</b></td><td>SHA-256 (FIPS 180-4)</td></tr>
            </table>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        """<div class="footer">
        ⚠️ <b>Disclaimer:</b> This tool is for data minimisation and safe testing environments.
        Process data locally for maximum security. For sensitive production use, deploy privately.<br>
        Built for <b>NDPR / NDPA 2023</b> compliance in Nigerian data centres and fintech.
        </div>""",
        unsafe_allow_html=True,
    )
