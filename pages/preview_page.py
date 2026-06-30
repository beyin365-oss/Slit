"""
Preview & Process page — before/after diff, chunked processing, DB audit save.
"""

import pandas as pd
import streamlit as st
from config import tier_config
from db.usage_db import increment_usage
from db.audit_db import save_audit_entry
from utils.redactor import DataRedactor
from utils.audit import AuditLogger
from utils.file_handler import write_file

PREVIEW_ROWS = 50
CHUNK        = 5_000


def preview_page() -> None:
    user = st.session_state.user

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Preview & Process</p>"
        "<p class='page-sub'>Side-by-side before/after (first 50 rows), then process the full dataset.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.get("active_file"):
        st.info("📤 Upload a file in **Upload & Redact** first.")
        return

    fname = st.session_state.active_file
    if fname not in st.session_state.get("uploaded_files", {}):
        st.info("📤 Upload a file in **Upload & Redact** first.")
        return

    fd      = st.session_state.uploaded_files[fname]
    df_orig = fd["df"]
    cfg     = st.session_state.get("redact_cfg", {})
    enabled = [c for c, v in cfg.items() if v.get("enabled") and c in df_orig.columns]

    if not enabled:
        st.warning("No columns enabled. Configure in **Upload & Redact**.")
        return

    # ── Before / After preview ────────────────────────────────────────────────
    df_prev = df_orig.head(PREVIEW_ROWS).copy()
    with st.spinner("Building preview…"):
        df_prev_red, _ = DataRedactor().redact(df_prev.copy(), cfg)

    cl, cr = st.columns(2)
    with cl:
        st.markdown("**Original** &nbsp;"
                    "<span class='badge badge-gray'>BEFORE</span>", unsafe_allow_html=True)
        st.dataframe(df_prev, use_container_width=True, height=360)
    with cr:
        st.markdown("**Redacted** &nbsp;"
                    "<span class='badge badge-blue'>AFTER</span>", unsafe_allow_html=True)
        try:
            def _hl(row):
                styles = []
                for col in row.index:
                    if col in enabled and col in df_prev_red.columns:
                        orig = str(df_prev.at[row.name, col]) if row.name in df_prev.index else ""
                        new  = str(df_prev_red.at[row.name, col]) if row.name in df_prev_red.index else ""
                        styles.append("background:rgba(37,99,235,0.18);color:#93c5fd" if orig != new else "")
                    else:
                        styles.append("")
                return styles
            st.dataframe(df_prev_red.style.apply(_hl, axis=1), use_container_width=True, height=360)
        except Exception:
            st.dataframe(df_prev_red, use_container_width=True, height=360)

    # Removed columns warning
    removed = [c for c, v in cfg.items()
               if v.get("enabled") and v.get("method") == "remove" and c in df_orig.columns]
    if removed:
        st.markdown(
            "<div class='card-warn'>⚠️ <b>Columns removed:</b> " +
            ", ".join(f"<code>{c}</code>" for c in removed) + "</div>",
            unsafe_allow_html=True)

    # Column method badges
    tags = " ".join(
        f"<span class='badge badge-blue'>{c} · {v['method']}</span>"
        for c, v in cfg.items() if v.get("enabled") and c in df_orig.columns
    )
    st.markdown(f"<div style='margin:0.5rem 0'>{tags}</div>", unsafe_allow_html=True)

    st.divider()

    # ── Process ───────────────────────────────────────────────────────────────
    st.markdown("### ⚡ Process Full Dataset")
    info = fd["info"]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Rows",        f"{len(df_orig):,}")
    p2.metric("Cols Redact", len(enabled))
    p3.metric("Size",        info["size"])
    p4.metric("Format",      info["format"])

    user_note = st.text_area("Audit note (optional)",
                             placeholder="e.g. Pre-production QA — NDPA compliant",
                             height=60)

    already_done = st.session_state.get("processed_df") is not None
    if already_done:
        st.markdown(
            "<div class='card-gold'>✅ <b>Already processed.</b> "
            "Download below or re-process.</div>",
            unsafe_allow_html=True)

    btn_lbl = "🔄 Re-process" if already_done else "⚡ Redact & Process"
    if st.button(btn_lbl, use_container_width=True):
        _run_processing(df_orig, cfg, enabled, fname, fd, user, user_note)

    # ── Download (after processing) ──────────────────────────────────────────
    if st.session_state.get("processed_df") is not None:
        _download_section(fname, fd["fmt"], st.session_state.processed_df)


def _run_processing(df_orig, cfg, enabled, fname, fd, user, user_note: str) -> None:
    n_rows   = len(df_orig)
    redactor = DataRedactor()
    chunks   = []
    stats: dict = {}

    pbar    = st.progress(0, text="Starting…")
    statbox = st.empty()

    try:
        if n_rows == 0:
            df_out = df_orig.copy()
            pbar.progress(1.0, text="Complete!")
            statbox.warning("File has 0 data rows — empty redacted file produced.")
        else:
            n_chunks = max(1, (n_rows + CHUNK - 1) // CHUNK)
            for i, start in enumerate(range(0, n_rows, CHUNK)):
                chunk = df_orig.iloc[start:start + CHUNK].copy()
                proc, chunk_stats = redactor.redact(chunk, cfg)
                chunks.append(proc)
                for col, s in chunk_stats.items():
                    if col not in stats:
                        stats[col] = {**s, "count": 0}
                    stats[col]["count"] += s.get("count", 0)
                pct  = (i + 1) / n_chunks
                done = start + len(chunk)
                pbar.progress(pct, text=f"Processing… {int(pct*100)}% ({done:,}/{n_rows:,})")
            df_out = pd.concat(chunks, ignore_index=True)
            pbar.progress(1.0, text="Complete!")
            statbox.success("✅ Redaction complete!")

        st.session_state.processed_df = df_out
        st.session_state.proc_stats   = stats

        # ── Update usage + audit log ─────────────────────────────────────────
        increment_usage(user["id"], files_delta=1, rows_delta=n_rows)

        auditor = AuditLogger()
        entry   = auditor.create_entry(
            session_id=user["id"],
            original_filename=fname,
            file_format=fd["fmt"],
            row_count=n_rows,
            column_count=len(df_orig.columns),
            redacted_columns={c: cfg[c] for c in enabled if c in cfg},
            stats=stats,
            file_hash=fd.get("hash", ""),
            user_note=user_note,
        )
        entry["audit_id"] = f"AUD-{user['id']}-{entry['audit_id'].split('-')[-1]}"
        save_audit_entry(user["id"], entry)

        # Stats
        total_vals = sum(s["count"] for s in stats.values())
        st.markdown("#### Summary")
        sc = st.columns(min(len(stats), 5))
        for i, (col, s) in enumerate(stats.items()):
            with sc[i % 5]:
                st.metric(col[:18], f"{s['count']:,}",
                          help=f"{s['method']} | {s['field_type']}")

        st.markdown(
            f"<div class='card-gold'>🏆 <b>{total_vals:,} values</b> redacted across "
            f"<b>{len(stats)}</b> column(s) in <b>{n_rows:,}</b> rows. "
            f"Audit ID: <code>{entry['audit_id']}</code></div>",
            unsafe_allow_html=True)

        _download_section(fname, fd["fmt"], df_out)

    except Exception as e:
        st.error(f"Processing error: {e}")
        raise


def _download_section(fname: str, fmt: str, df_out: pd.DataFrame) -> None:
    st.markdown("#### ⬇️ Download Redacted File")
    out_bytes, mime, out_name = write_file(df_out, fmt, fname)
    dc1, dc2 = st.columns(2)
    with dc1:
        st.download_button(f"⬇️ Download ({fmt.upper()})",
                           data=out_bytes, file_name=out_name, mime=mime,
                           use_container_width=True)
    with dc2:
        if fmt != "csv":
            csv_b, _, csv_n = write_file(df_out, "csv", fname)
            st.download_button("⬇️ Download (CSV)",
                               data=csv_b, file_name=csv_n, mime="text/csv",
                               use_container_width=True)
