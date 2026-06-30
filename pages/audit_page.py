"""
Audit Log page — searchable, filterable DB log with CSV/PDF export.
"""

from datetime import datetime
import pandas as pd
import streamlit as st
from config import tier_config
from db.audit_db import get_user_audit_log
from utils.audit import AuditLogger


def audit_page() -> None:
    user = st.session_state.user
    tier = user["tier"]
    cfg  = tier_config(tier)

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Audit Log</p>"
        "<p class='page-sub'>All redaction events — searchable, filterable, and exportable. Persisted in database.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    logs = get_user_audit_log(user["id"], limit=500)

    if not logs:
        st.markdown(
            "<div class='card' style='text-align:center;padding:3rem'>"
            "<div style='font-size:2.5rem'>📋</div>"
            "<p style='font-weight:600;margin:0.5rem 0'>No audit entries yet</p>"
            "<p style='color:#7a90b8;font-size:0.85rem'>Process a file to create your first audit entry.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Summary metrics ──────────────────────────────────────────────────────
    total_rows = sum(e.get("rows_processed", 0) or 0 for e in logs)
    total_vals = sum(e.get("values_redacted", 0) or 0 for e in logs)
    lm1, lm2, lm3, lm4 = st.columns(4)
    lm1.metric("Total Entries",    len(logs))
    lm2.metric("Files Processed",  len(set(e["original_filename"] for e in logs)))
    lm3.metric("Rows Processed",   f"{total_rows:,}")
    lm4.metric("Values Redacted",  f"{total_vals:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Search & Filter ──────────────────────────────────────────────────────
    sf1, sf2, sf3 = st.columns([3, 2, 1])
    with sf1:
        q = st.text_input("🔍 Search", placeholder="filename, audit ID, note…",
                          label_visibility="collapsed")
    with sf2:
        all_fmts = sorted(set(e.get("file_format","") for e in logs if e.get("file_format")))
        fmt_f    = st.multiselect("Format", all_fmts, label_visibility="collapsed",
                                  placeholder="Filter by format…")
    with sf3:
        if st.button("Clear", use_container_width=True):
            st.rerun()

    # Apply
    filtered = logs
    if q.strip():
        ql = q.strip().lower()
        filtered = [e for e in filtered
                    if ql in (e.get("original_filename") or "").lower()
                    or ql in (e.get("audit_id") or "").lower()
                    or ql in (e.get("user_note") or "").lower()
                    or ql in (e.get("redaction_summary") or "").lower()]
    if fmt_f:
        filtered = [e for e in filtered if e.get("file_format","") in fmt_f]

    st.caption(f"Showing {len(filtered)} of {len(logs)} entries")

    if not filtered:
        st.info("No entries match your search.")
        return

    # ── Table ─────────────────────────────────────────────────────────────────
    show_cols = ["audit_id","timestamp","original_filename","file_format",
                 "rows_processed","columns_redacted","values_redacted","user_note"]
    df_log = pd.DataFrame(filtered)
    cols_present = [c for c in show_cols if c in df_log.columns]
    st.dataframe(df_log[cols_present], use_container_width=True, hide_index=True, height=300)

    # ── Detail view ──────────────────────────────────────────────────────────
    with st.expander("🔎 Entry Detail"):
        entry_ids = [e.get("audit_id","") for e in filtered]
        sel_id    = st.selectbox("Entry", entry_ids, label_visibility="collapsed")
        entry     = next((e for e in filtered if e.get("audit_id") == sel_id), None)
        if entry:
            detail_rows = [
                ("Audit ID",          entry.get("audit_id","")),
                ("Timestamp",         entry.get("timestamp","")[:19]),
                ("File",              entry.get("original_filename","")),
                ("Format",            entry.get("file_format","")),
                ("Rows Processed",    f"{entry.get('rows_processed',0):,}"),
                ("Columns Redacted",  str(entry.get("columns_redacted",""))),
                ("Values Redacted",   f"{entry.get('values_redacted',0):,}"),
                ("SHA-256 (file)",    (entry.get("file_sha256","") or "—")[:48]),
                ("User Note",         entry.get("user_note","") or "—"),
            ]
            for k, v in detail_rows:
                ca, cb = st.columns([2, 5])
                ca.markdown(f"**{k}**")
                cb.markdown(f"`{v}`" if len(str(v)) > 30 else str(v))
            summary = entry.get("redaction_summary","")
            if summary:
                st.markdown("**Redaction Summary:**")
                for part in summary.split(" | "):
                    st.markdown(f"- {part}")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("#### Export")
    auditor   = AuditLogger()
    sid       = str(user["id"])
    e1, e2, e3 = st.columns(3)

    # Convert DB rows to AuditLogger format
    def _db_to_audit(entries: list) -> list:
        out = []
        for e in entries:
            out.append({
                "audit_id":             e.get("audit_id",""),
                "timestamp":            e.get("timestamp",""),
                "session_id":           sid,
                "original_filename":    e.get("original_filename",""),
                "file_format":          e.get("file_format",""),
                "rows_processed":       e.get("rows_processed",0),
                "columns_total":        e.get("columns_total",0),
                "columns_redacted":     e.get("columns_redacted",0),
                "values_redacted_total":e.get("values_redacted",0),
                "file_sha256":          e.get("file_sha256",""),
                "redaction_summary":    e.get("redaction_summary",""),
                "user_note":            e.get("user_note",""),
                "ndpr_compliance":      e.get("ndpr_note","NDPA 2023"),
            })
        return out

    with e1:
        csv_b = auditor.to_csv_bytes(_db_to_audit(filtered))
        st.download_button(
            "📊 Export Filtered (CSV)", data=csv_b,
            file_name=f"ndpr_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", use_container_width=True)

    with e2:
        all_csv = auditor.to_csv_bytes(_db_to_audit(logs))
        st.download_button(
            "📊 Export All (CSV)", data=all_csv,
            file_name=f"ndpr_audit_all_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", use_container_width=True)

    with e3:
        if not cfg["audit_pdf"]:
            st.markdown(
                "<div class='card-warn' style='padding:0.5rem 0.8rem;font-size:0.82rem'>"
                "PDF export is available on <b>Starter</b> plan and above.</div>",
                unsafe_allow_html=True)
            if st.button("⬆ Upgrade", use_container_width=True, key="upg_pdf"):
                st.session_state.page = "Billing"; st.rerun()
        else:
            try:
                pdf_b = auditor.to_pdf_bytes(_db_to_audit(filtered), sid)
                st.download_button(
                    "📑 Compliance Report (PDF)", data=pdf_b,
                    file_name=f"ndpr_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", use_container_width=True)
            except Exception as ex:
                st.caption(f"PDF unavailable: {ex}")
