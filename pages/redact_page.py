"""
Upload & Redact page — tier-enforced file upload, PII detection, column configuration.
"""

import streamlit as st
from config import (
    TIERS, tier_config, METHODS, METHOD_ICONS,
    can_upload, can_process_rows, can_use_format, FORMAT_LABELS
)
from db.presets_db import (
    save_preset, load_preset, list_presets, count_presets, delete_preset
)
from db.usage_db import get_usage
from utils.detector import SensitiveDataDetector
from utils.file_handler import read_file, file_info, hash_file, MAX_FILE_SIZE_MB


def _badge(text: str, kind: str = "blue") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def _conf_badge(conf: float) -> str:
    pct = int(conf * 100)
    if conf >= 0.85:
        return _badge(f"✓ {pct}%", "green")
    elif conf >= 0.6:
        return _badge(f"~ {pct}%", "gold")
    return _badge(f"? {pct}%", "gray")


def _init_state() -> None:
    for k, v in {
        "uploaded_files": {},
        "active_file": None,
        "detected_cols": {},
        "redact_cfg": {},
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


def redact_page() -> None:
    _init_state()
    user  = st.session_state.user
    tier  = user["tier"]
    cfg_t = tier_config(tier)

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Upload & Redact</p>"
        "<p class='page-sub'>Upload your file, review auto-detected PII, and configure redaction per column.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Usage gate ────────────────────────────────────────────────────────────
    usage = get_usage(user["id"])
    ok, msg = can_upload(tier, usage["files_processed"])
    if not ok:
        _upgrade_wall(msg)
        return

    # ── File upload ───────────────────────────────────────────────────────────
    allowed_ext = []
    for fmt in cfg_t["allowed_formats"]:
        if fmt == "csv":    allowed_ext += ["csv"]
        elif fmt == "excel": allowed_ext += ["xlsx", "xls"]
        elif fmt == "json": allowed_ext += ["json"]

    tier_fmt_label = ", ".join(FORMAT_LABELS[f] for f in cfg_t["allowed_formats"])
    st.markdown(
        f"<p style='color:#7a90b8;font-size:0.85rem'>Accepted formats: {tier_fmt_label} "
        f"· Max {MAX_FILE_SIZE_MB} MB per file · "
        f"{'Unlimited' if not cfg_t['max_files_month'] else str(cfg_t['max_files_month'])} uploads/month</p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop files here", type=allowed_ext,
        accept_multiple_files=True, label_visibility="collapsed",
    )

    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.uploaded_files:
                continue
            raw = f.read()

            # Size check
            if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"**{f.name}** exceeds {MAX_FILE_SIZE_MB} MB — skipped.")
                continue

            # Format tier check
            ext = f.name.rsplit(".", 1)[-1].lower()
            fmt_key = "excel" if ext in ("xlsx", "xls") else ext
            fmt_ok, fmt_msg = can_use_format(tier, fmt_key)
            if not fmt_ok:
                _upgrade_wall(fmt_msg)
                continue

            with st.spinner(f"Parsing {f.name}…"):
                try:
                    df, fmt = read_file(raw, f.name)
                    info    = file_info(df, f.name, raw)
                    fhash   = hash_file(raw)

                    # Row count tier check
                    rows_ok, rows_msg = can_process_rows(tier, len(df))
                    if not rows_ok:
                        _upgrade_wall(rows_msg)
                        continue

                    st.session_state.uploaded_files[f.name] = {
                        "df": df, "fmt": fmt, "raw": raw, "info": info, "hash": fhash,
                    }
                    if not st.session_state.active_file:
                        _set_active(f.name, df)
                    st.success(f"✓ **{f.name}** — {info['rows']:,} rows × {info['columns']} columns")
                except ValueError as e:
                    st.error(f"**{f.name}**: {e}")

    if not st.session_state.uploaded_files:
        st.markdown(
            "<div class='card' style='text-align:center;padding:3rem'>"
            "<div style='font-size:3rem'>📂</div>"
            f"<p style='font-weight:600'>No file loaded</p>"
            f"<p style='color:#7a90b8;font-size:0.85rem'>Supports {tier_fmt_label} · max {MAX_FILE_SIZE_MB} MB</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Active file selector ──────────────────────────────────────────────────
    files = list(st.session_state.uploaded_files.keys())
    if len(files) > 1:
        active = st.selectbox("Active file", files,
            index=files.index(st.session_state.active_file) if st.session_state.active_file in files else 0)
        if active != st.session_state.active_file:
            _set_active(active, st.session_state.uploaded_files[active]["df"])
            st.rerun()

    fname = st.session_state.active_file
    if not fname or fname not in st.session_state.uploaded_files:
        return

    fd   = st.session_state.uploaded_files[fname]
    df   = fd["df"]
    info = fd["info"]
    cfg  = st.session_state.redact_cfg
    det  = st.session_state.detected_cols

    # ── File metrics ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Rows",    f"{info['rows']:,}")
    m2.metric("Columns", info["columns"])
    m3.metric("Format",  info["format"])
    m4.metric("Size",    info["size"])
    m5.metric("PII Detected", len(det))

    with st.expander("🔑 File Integrity (SHA-256)", expanded=False):
        st.code(fd["hash"], language=None)

    st.divider()

    # ── Controls row ─────────────────────────────────────────────────────────
    hc1, hc2, hc3, hc4 = st.columns([4, 1, 1, 1])
    n_enabled = sum(1 for c in cfg.values() if c.get("enabled"))
    with hc1:
        st.markdown(
            f"<div class='card-blue' style='padding:0.65rem 1rem;margin:0'>"
            f"🔍 <b>{len(det)}</b> PII columns detected &nbsp;·&nbsp; "
            f"<b>{n_enabled}</b> enabled for redaction</div>",
            unsafe_allow_html=True,
        )
    with hc2:
        if st.button("🔍 Re-detect", use_container_width=True):
            _set_active(fname, df); st.rerun()
    with hc3:
        if st.button("↩ Reset", use_container_width=True):
            st.session_state.redact_cfg = {}
            _set_active(fname, df); st.rerun()
    with hc4:
        if st.button("✅ All On", use_container_width=True):
            for c in cfg: cfg[c]["enabled"] = True
            st.rerun()

    # ── Accordions ──────────────────────────────────────────────────────────
    with st.expander("🌐 Global Method Override"):
        ga, gb = st.columns([3, 1])
        with ga:
            gm = st.selectbox("Method", list(METHODS.keys()),
                              format_func=lambda x: f"{METHOD_ICONS[x]} {METHODS[x]}",
                              key="global_method_sel", label_visibility="collapsed")
        with gb:
            if st.button("Apply to All", use_container_width=True):
                for c in cfg:
                    if cfg[c].get("enabled"): cfg[c]["method"] = gm
                st.rerun()

    with st.expander("➕ Add column manually"):
        non_cfg = [c for c in df.columns if c not in cfg]
        if non_cfg:
            ca, cb = st.columns([4, 1])
            with ca:
                new_col = st.selectbox("Column", non_cfg, label_visibility="collapsed")
            with cb:
                if st.button("Add", use_container_width=True):
                    cfg[new_col] = {"enabled": True, "method": "mask", "field_type": "generic",
                                    "regex_pattern": "", "regex_replacement": "[REDACTED]"}
                    st.rerun()
        else:
            st.success("All columns configured.")

    # ── Presets ───────────────────────────────────────────────────────────────
    with st.expander("💾 Presets"):
        max_p    = cfg_t["max_presets"]
        n_saved  = count_presets(user["id"])
        saved    = list_presets(user["id"])

        pc1, pc2, pc3, pc4 = st.columns([2, 1, 2, 1])
        with pc1:
            tpl_name = st.text_input("Save as", placeholder="e.g. Fintech KYC",
                                     label_visibility="collapsed")
        with pc2:
            if st.button("💾 Save", use_container_width=True):
                if max_p is not None and n_saved >= max_p:
                    st.warning(f"Preset limit ({max_p}) reached. Upgrade to save more.")
                elif tpl_name.strip():
                    ok, msg = save_preset(user["id"], tpl_name.strip(),
                                          {c: dict(v) for c, v in cfg.items()})
                    (st.success if ok else st.error)(msg)
                else:
                    st.warning("Enter a preset name.")
        with pc3:
            if saved:
                chosen_p = st.selectbox("Load preset", ["— select —"] + saved,
                                        label_visibility="collapsed")
            else:
                chosen_p = "— select —"
                st.caption("No presets saved yet.")
        with pc4:
            if saved and st.button("📥 Load", use_container_width=True):
                if chosen_p != "— select —":
                    loaded = load_preset(user["id"], chosen_p)
                    if loaded:
                        for c, cv in loaded.items():
                            if c in cfg: cfg[c].update(cv)
                        st.success(f"Loaded '{chosen_p}'")
                        st.rerun()

    st.divider()

    # ── Column config table ──────────────────────────────────────────────────
    if not cfg:
        st.markdown(
            "<div class='card' style='text-align:center;padding:2rem'>"
            "<p style='color:#7a90b8'>No columns configured. Use 'Add column manually' above.</p>"
            "</div>", unsafe_allow_html=True)
        return

    h = st.columns([0.35, 2.2, 2.0, 2.4, 1.4, 0.8])
    for hcol, lbl in zip(h, ["", "Column", "Detected Type", "Method", "Confidence", ""]):
        hcol.markdown(
            f"<span style='font-size:0.75rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.07em;color:#7a90b8'>{lbl}</span>",
            unsafe_allow_html=True)
    st.markdown("<hr style='margin:3px 0 6px'>", unsafe_allow_html=True)

    for col in list(cfg.keys()):
        c_cfg    = cfg[col]
        det_info = det.get(col, {})
        conf     = det_info.get("confidence", 0)
        type_lbl = det_info.get("label", "Custom / Manual")

        row = st.columns([0.35, 2.2, 2.0, 2.4, 1.4, 0.8])
        with row[0]:
            en = st.checkbox("##en", value=c_cfg.get("enabled", True),
                             key=f"en_{col}", label_visibility="collapsed")
            c_cfg["enabled"] = en
        with row[1]:
            src_icon = "📌" if "name" in det_info.get("source","") else "🔍"
            st.markdown(f"`{col}` &nbsp;{src_icon}", unsafe_allow_html=True)
        with row[2]:
            st.markdown(f"<span style='font-size:0.84rem'>{type_lbl}</span>",
                        unsafe_allow_html=True)
        with row[3]:
            cur_m = c_cfg.get("method", "mask")
            chosen = st.selectbox("##m", list(METHODS.keys()),
                                  format_func=lambda x: f"{METHOD_ICONS[x]} {METHODS[x]}",
                                  index=list(METHODS.keys()).index(cur_m) if cur_m in METHODS else 0,
                                  key=f"mth_{col}", label_visibility="collapsed")
            c_cfg["method"] = chosen
            if chosen == "regex":
                c_cfg["regex_pattern"]     = st.text_input("Pattern", value=c_cfg.get("regex_pattern",""),
                                                            key=f"rgxp_{col}", placeholder=r"\d{10}")
                c_cfg["regex_replacement"] = st.text_input("Replacement", value=c_cfg.get("regex_replacement","[REDACTED]"),
                                                            key=f"rgxr_{col}")
        with row[4]:
            st.markdown(_conf_badge(conf) if conf else _badge("manual","gray"),
                        unsafe_allow_html=True)
        with row[5]:
            if st.button("✕", key=f"rm_{col}"):
                del st.session_state.redact_cfg[col]; st.rerun()
        st.markdown("<hr style='margin:2px 0'>", unsafe_allow_html=True)


def _set_active(fname: str, df) -> None:
    st.session_state.active_file = fname
    det = SensitiveDataDetector().detect(df)
    st.session_state.detected_cols = det
    cfg = st.session_state.redact_cfg
    for col, info in det.items():
        if col not in cfg:
            cfg[col] = {"enabled": True, "method": "mask",
                        "field_type": info["type"],
                        "regex_pattern": "", "regex_replacement": "[REDACTED]"}
    st.session_state.processed_df  = None
    st.session_state.proc_stats    = {}


def _upgrade_wall(msg: str) -> None:
    st.markdown(
        f"<div class='card-warn'>"
        f"⚠️ {msg}<br>"
        f"<small style='color:#7a90b8'>Go to <b>Billing</b> to upgrade your plan.</small>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("⬆ View Plans & Upgrade"):
        st.session_state.page = "Billing"; st.rerun()
