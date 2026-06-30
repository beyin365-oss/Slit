"""
Admin panel — user management, usage overview, revenue, platform audit log.
"""

import pandas as pd
import streamlit as st
from config import TIERS
from db.auth_db import list_all_users, set_user_active, set_user_tier
from db.usage_db import get_platform_usage
from db.audit_db import get_all_audit_log, count_audit_entries
from db.subscriptions_db import revenue_summary


def admin_page() -> None:
    user = st.session_state.user
    if user.get("role") != "admin":
        st.error("Access denied. Admins only.")
        return

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>🔧 Admin Panel</p>"
        "<p class='page-sub'>Platform management — users, usage, revenue, audit.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Platform overview ─────────────────────────────────────────────────────
    all_users = list_all_users()
    revenue   = revenue_summary()
    n_audits  = count_audit_entries()

    total_revenue = sum(v["total_ngn"] for v in revenue.values())
    paying_users  = sum(1 for u in all_users if u.get("tier","free") not in ("free","enterprise"))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Users",      len(all_users))
    m2.metric("Paying Users",     paying_users)
    m3.metric("Total Revenue",    f"₦{total_revenue:,}")
    m4.metric("Audit Entries",    f"{n_audits:,}")
    m5.metric("Active Subs",      sum(v["count"] for v in revenue.values()))

    tab_users, tab_usage, tab_revenue, tab_audit = st.tabs([
        "👥 Users", "📊 Usage", "💰 Revenue", "📋 Audit Log"
    ])

    # ── Users ─────────────────────────────────────────────────────────────────
    with tab_users:
        sq, sstat = st.columns([3, 1])
        with sq:
            search = st.text_input("Search users", placeholder="email or name…",
                                   label_visibility="collapsed")
        with sstat:
            tier_filter = st.selectbox("Tier", ["All"] + list(TIERS.keys()),
                                       label_visibility="collapsed")

        filtered = all_users
        if search.strip():
            ql = search.strip().lower()
            filtered = [u for u in filtered
                        if ql in u["email"].lower() or ql in u["full_name"].lower()]
        if tier_filter != "All":
            filtered = [u for u in filtered if u.get("tier","free") == tier_filter]

        st.caption(f"{len(filtered)} user(s)")

        for u in filtered:
            tier  = u.get("tier", "free")
            tclr  = TIERS.get(tier, {}).get("badge_colour","#6b7280")
            acol1, acol2, acol3, acol4, acol5 = st.columns([3, 1.2, 1.2, 1.2, 1.2])

            with acol1:
                active_icon = "🟢" if u["is_active"] else "🔴"
                st.markdown(
                    f"{active_icon} **{u['full_name']}** · "
                    f"<span style='color:#7a90b8;font-size:0.82rem'>{u['email']}</span><br>"
                    f"<span style='background:{tclr}22;color:{tclr};border-radius:10px;"
                    f"padding:1px 8px;font-size:0.72rem;font-weight:700'>{tier.capitalize()}</span>"
                    f"<span style='color:#7a90b8;font-size:0.75rem;margin-left:0.5rem'>"
                    f"Joined: {u['created_at'][:10]}</span>",
                    unsafe_allow_html=True)

            with acol2:
                new_tier = st.selectbox("Tier", list(TIERS.keys()),
                                        index=list(TIERS.keys()).index(tier) if tier in TIERS else 0,
                                        key=f"adm_tier_{u['id']}", label_visibility="collapsed")

            with acol3:
                if st.button("Apply", key=f"adm_set_{u['id']}", use_container_width=True):
                    if u["id"] != user["id"]:
                        set_user_tier(u["id"], new_tier)
                        st.success(f"Updated {u['email']} → {new_tier}")
                        st.rerun()
                    else:
                        st.warning("Cannot change your own tier here.")

            with acol4:
                active_lbl = "🔴 Deactivate" if u["is_active"] else "🟢 Activate"
                if st.button(active_lbl, key=f"adm_act_{u['id']}", use_container_width=True):
                    if u["id"] != user["id"]:
                        set_user_active(u["id"], not u["is_active"])
                        st.rerun()

            with acol5:
                role_lbl = "👤 " + (u.get("role") or "user").capitalize()
                st.markdown(
                    f"<span style='font-size:0.82rem;color:#7a90b8'>{role_lbl}</span>",
                    unsafe_allow_html=True)

            st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    # ── Usage ─────────────────────────────────────────────────────────────────
    with tab_usage:
        usage_data = get_platform_usage()
        if usage_data:
            df_u = pd.DataFrame(usage_data)
            df_u.columns = [c.replace("_"," ").title() for c in df_u.columns]
            st.dataframe(df_u, use_container_width=True, hide_index=True)
        else:
            st.info("No usage data yet.")

    # ── Revenue ───────────────────────────────────────────────────────────────
    with tab_revenue:
        if not revenue:
            st.info("No subscription data.")
        else:
            rev_rows = []
            for tier, data in revenue.items():
                rev_rows.append({
                    "Plan":        TIERS.get(tier,{}).get("name",tier),
                    "Subscribers": data["count"],
                    "Revenue (₦)": f"₦{data['total_ngn']:,}",
                    "MRR (₦)":     f"₦{data['total_ngn']:,}",
                })
            rev_rows.append({
                "Plan":        "**TOTAL**",
                "Subscribers": sum(v["count"] for v in revenue.values()),
                "Revenue (₦)": f"₦{total_revenue:,}",
                "MRR (₦)":     f"₦{total_revenue:,}",
            })
            st.dataframe(pd.DataFrame(rev_rows), use_container_width=True, hide_index=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='card-gold'>"
                f"💰 <b>Total Monthly Recurring Revenue: ₦{total_revenue:,}</b>"
                f"</div>",
                unsafe_allow_html=True)

    # ── Audit log ─────────────────────────────────────────────────────────────
    with tab_audit:
        aq = st.text_input("Search audit log", placeholder="email, filename, audit ID…",
                           label_visibility="collapsed")
        all_logs = get_all_audit_log(limit=500)

        if aq.strip():
            ql = aq.strip().lower()
            all_logs = [e for e in all_logs
                        if ql in (e.get("email","")).lower()
                        or ql in (e.get("original_filename","")).lower()
                        or ql in (e.get("audit_id","")).lower()]

        st.caption(f"{len(all_logs)} entries")
        show_cols = ["audit_id","timestamp","email","original_filename",
                     "file_format","rows_processed","values_redacted"]
        if all_logs:
            df_al = pd.DataFrame(all_logs)
            cols_p = [c for c in show_cols if c in df_al.columns]
            st.dataframe(df_al[cols_p], use_container_width=True, hide_index=True, height=400)
        else:
            st.info("No audit entries match.")
