"""
User dashboard: usage stats, subscription status, recent activity.
"""

import streamlit as st
import pandas as pd
from config import TIERS, tier_config
from db.usage_db import get_usage, get_all_time_usage
from db.audit_db import get_user_audit_log


def _tier_badge(tier: str) -> str:
    cfg = TIERS.get(tier, TIERS["free"])
    colour = cfg["badge_colour"]
    name   = cfg["name"]
    return (f"<span style='background:{colour}22;color:{colour};"
            f"border:1px solid {colour}55;border-radius:20px;"
            f"padding:3px 12px;font-size:0.78rem;font-weight:700'>{name}</span>")


def dashboard_page() -> None:
    user = st.session_state.user
    tier = user["tier"]
    cfg  = tier_config(tier)

    # ── Header ──
    st.markdown(
        f"<div class='page-header'>"
        f"<p class='page-title'>Welcome back, {user['full_name'].split()[0]} 👋</p>"
        f"<p class='page-sub'>"
        f"{_tier_badge(tier)}"
        f"&nbsp;&nbsp;Session ready — start redacting or view your usage below."
        f"</p></div>",
        unsafe_allow_html=True,
    )

    # ── Monthly usage ──
    usage    = get_usage(user["id"])
    alltime  = get_all_time_usage(user["id"])
    files_used = usage["files_processed"]
    rows_used  = usage["rows_processed"]
    files_max  = cfg["max_files_month"]
    rows_max   = cfg["max_rows"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files This Month",   f"{files_used:,}", help=f"Limit: {files_max if files_max else '∞'}")
    c2.metric("Rows This Month",    f"{rows_used:,}",  help=f"Limit: {rows_max if rows_max else '∞'}")
    c3.metric("Total Files (All Time)", f"{alltime['total_files']:,}")
    c4.metric("Total Rows (All Time)",  f"{alltime['total_rows']:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Usage progress bars ──
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"**📁 File Uploads This Month**")
        if files_max:
            pct = min(files_used / files_max, 1.0)
            colour = "#ef4444" if pct >= 0.9 else ("#f0a500" if pct >= 0.7 else "#2563eb")
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:0.82rem;color:#7a90b8'>"
                f"<span>{files_used} used</span><span>{files_max} limit</span></div>",
                unsafe_allow_html=True,
            )
            st.progress(pct)
            if pct >= 1.0:
                st.warning("⚠️ Monthly limit reached. Upgrade to continue uploading.")
        else:
            st.markdown(
                f"<p style='color:#10b981;font-weight:700'>{files_used:,} / Unlimited</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_u2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"**📊 Rows Processed This Month**")
        if rows_max:
            pct = min(rows_used / rows_max, 1.0)
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:0.82rem;color:#7a90b8'>"
                f"<span>{rows_used:,} processed</span><span>{rows_max:,} limit</span></div>",
                unsafe_allow_html=True,
            )
            st.progress(pct)
        else:
            st.markdown(
                f"<p style='color:#10b981;font-weight:700'>{rows_used:,} / Unlimited</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Plan features summary ──
    col_f, col_a = st.columns([1, 2])

    with col_f:
        _files_lbl = "∞" if not cfg["max_files_month"] else str(cfg["max_files_month"])
        _rows_lbl  = "∞" if not cfg["max_rows"] else f"{cfg['max_rows']:,}"
        _fmts_lbl  = ", ".join(fmt.upper() for fmt in cfg["allowed_formats"])
        _pdf_lbl   = "✓" if cfg["audit_pdf"] else "✗"
        _api_lbl   = "✓" if cfg["api_access"] else "✗"
        st.markdown(
            f"<div class='card-gold'>"
            f"<b>Your Plan: {cfg['name']}</b><br>"
            f"<span style='color:#7a90b8;font-size:0.85rem'>{cfg['description']}</span>"
            f"<hr style='border-color:#f0a50033;margin:0.7rem 0'>"
            f"<ul style='margin:0;padding-left:1.2rem;font-size:0.85rem;line-height:2'>"
            f"<li>{_files_lbl} files / month</li>"
            f"<li>{_rows_lbl} max rows</li>"
            f"<li>Formats: {_fmts_lbl}</li>"
            f"<li>PDF reports: {_pdf_lbl}</li>"
            f"<li>API access: {_api_lbl}</li>"
            f"</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if tier == "free":
            if st.button("⬆ Upgrade Plan", use_container_width=True):
                st.session_state.page = "Billing"
                st.rerun()

    with col_a:
        # ── Recent activity ──
        logs = get_user_audit_log(user["id"], limit=5)
        st.markdown("**🕐 Recent Activity**")
        if not logs:
            st.markdown(
                "<div class='card' style='text-align:center;padding:1.5rem'>"
                "<p style='color:#7a90b8'>No activity yet. Upload your first file to get started.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            for log in logs:
                fname  = log.get("original_filename", "—")[:30]
                ts     = log.get("timestamp", "")[:16]
                rows   = log.get("rows_processed", 0)
                vals   = log.get("values_redacted", 0)
                fmt    = log.get("file_format", "").upper()
                st.markdown(
                    f"<div class='card' style='padding:0.65rem 1rem;margin-bottom:0.5rem'>"
                    f"<span style='font-weight:600'>{fname}</span>"
                    f"<span style='float:right;font-size:0.78rem;color:#7a90b8'>{ts}</span><br>"
                    f"<span style='font-size:0.8rem;color:#7a90b8'>"
                    f"{fmt} · {rows:,} rows · {vals:,} values redacted</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
