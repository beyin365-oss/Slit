"""
Billing page: plan comparison, Paystack integration, subscription management.
"""

import streamlit as st
from config import TIERS, tier_config
from db.subscriptions_db import (
    get_subscription, set_subscription, cancel_subscription, subscription_history
)
from utils.paystack import (
    initialize_transaction, verify_transaction,
    generate_reference, tier_amount, is_configured
)


def billing_page() -> None:
    user = st.session_state.user
    tier = user["tier"]

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Billing & Subscription</p>"
        "<p class='page-sub'>Manage your plan, view payment history, and upgrade anytime.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    sub = get_subscription(user["id"])

    # ── Current plan ──
    cfg = tier_config(tier)
    st.markdown(
        f"<div class='card-gold'>"
        f"<b>Current Plan: {cfg['name']}</b> &nbsp;·&nbsp; {cfg['price_label']}<br>"
        f"<span style='color:#7a90b8;font-size:0.85rem'>{cfg['description']}</span>"
        f"{'<br><span style=\"font-size:0.8rem;color:#7a90b8\">Subscription expires: ' + (sub['end_date'] or 'N/A') + '</span>' if sub and sub.get('end_date') else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Compare Plans")
    _plan_table(tier)

    st.divider()

    # ── Upgrade / Subscribe ──
    if tier in ("free", "starter"):
        st.markdown("### Upgrade Your Plan")
        upgrade_options = {
            "starter": "Starter — ₦4,900/month",
            "pro":     "Pro — ₦14,900/month",
        }
        if tier == "starter":
            upgrade_options = {"pro": "Pro — ₦14,900/month"}

        chosen = st.selectbox("Select plan to upgrade to",
                              list(upgrade_options.values()),
                              label_visibility="collapsed")
        target_tier = [k for k, v in upgrade_options.items() if v == chosen][0]
        target_amt  = tier_amount(target_tier)

        if not is_configured():
            st.markdown(
                "<div class='card-warn'>"
                "⚠️ <b>Test / Demo mode:</b> Paystack keys not configured. "
                "Set <code>PAYSTACK_SECRET_KEY</code> and <code>PAYSTACK_PUBLIC_KEY</code> "
                "env vars to enable live payments. In demo mode you can simulate upgrade below."
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("**Demo Upgrade** (no payment — for testing only)")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"✅ Simulate Upgrade to {chosen}", use_container_width=True):
                    set_subscription(user["id"], target_tier, "DEMO-REF", target_amt)
                    st.session_state.user["tier"] = target_tier
                    st.success(f"✅ Upgraded to **{TIERS[target_tier]['name']}** (demo mode).")
                    st.rerun()
        else:
            ref = generate_reference(user["id"], target_tier)
            if "pending_ref" not in st.session_state:
                st.session_state.pending_ref = None

            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"💳 Pay ₦{target_amt:,} with Paystack", use_container_width=True):
                    result = initialize_transaction(user["email"], target_amt, ref)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.pending_ref = result.get("reference", ref)
                        auth_url = result.get("authorization_url", "")
                        st.markdown(
                            f"<a href='{auth_url}' target='_blank'>"
                            f"<button style='width:100%;background:#f0a500;color:#0a1226;font-weight:700;"
                            f"padding:0.6rem;border:none;border-radius:7px;cursor:pointer;font-size:1rem'>"
                            f"🔗 Open Paystack Payment Page</button></a>",
                            unsafe_allow_html=True,
                        )

            # Verify
            with c2:
                verify_ref = st.text_input("Enter payment reference to verify",
                                           value=st.session_state.pending_ref or "",
                                           placeholder="NDPR-PRO-1-...")
                if st.button("✅ Verify Payment", use_container_width=True):
                    result = verify_transaction(verify_ref)
                    if result.get("success"):
                        amt = result.get("amount_ngn", 0)
                        set_subscription(user["id"], target_tier, verify_ref, amt)
                        st.session_state.user["tier"] = target_tier
                        st.success(f"✅ Payment verified! Upgraded to **{TIERS[target_tier]['name']}**.")
                        st.session_state.pending_ref = None
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('error', 'Payment not verified.')}")

    elif tier == "pro":
        st.markdown(
            "<div class='card-blue'>"
            "🏆 You're on the <b>Pro</b> plan. For Enterprise (API access, SLA, on-premise), "
            "contact <a href='mailto:enterprise@ndpr.ng'>enterprise@ndpr.ng</a>."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Cancel ──
    if tier not in ("free", "enterprise"):
        st.divider()
        with st.expander("⚠️ Cancel Subscription"):
            st.warning("Cancelling will downgrade you to the Free plan immediately.")
            if st.button("Cancel Subscription", type="primary"):
                cancel_subscription(user["id"])
                st.session_state.user["tier"] = "free"
                st.success("Subscription cancelled. You are now on the Free plan.")
                st.rerun()

    # ── Payment history ──
    st.divider()
    st.markdown("### Payment History")
    history = subscription_history(user["id"])
    if history:
        rows = [
            {
                "Date":      h["created_at"][:10],
                "Plan":      h["tier"].capitalize(),
                "Status":    h["status"].capitalize(),
                "Amount":    f"₦{h['amount_ngn']:,}" if h.get("amount_ngn") else "—",
                "Reference": h.get("paystack_ref") or "—",
            }
            for h in history
        ]
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No payment history.")


def _plan_table(current_tier: str) -> None:
    cols = st.columns(4)
    tier_order = ["free", "starter", "pro", "enterprise"]
    for col, tk in zip(cols, tier_order):
        cfg = TIERS[tk]
        is_current = tk == current_tier
        border = "border:2px solid #f0a500" if is_current else "border:1px solid #1e3560"
        files  = "∞" if not cfg["max_files_month"] else f"{cfg['max_files_month']}"
        rows   = "∞" if not cfg["max_rows"]         else f"{cfg['max_rows']:,}"
        fmts   = ", ".join(f.upper() for f in cfg["allowed_formats"])
        price  = cfg["price_label"]

        col.markdown(
            f"<div class='card' style='{border};position:relative'>"
            f"{'<div style=\"position:absolute;top:8px;right:8px;background:#f0a500;color:#0a1226;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:700\">CURRENT</div>' if is_current else ''}"
            f"<p style='font-weight:800;font-size:1rem;margin:0'>{cfg['name']}</p>"
            f"<p style='color:#f0a500;font-weight:700;margin:0.2rem 0'>{price}</p>"
            f"<p style='color:#7a90b8;font-size:0.78rem;margin:0 0 0.7rem'>{cfg['description']}</p>"
            f"<ul style='font-size:0.82rem;line-height:2;padding-left:1.1rem;margin:0'>"
            f"<li>{files} files/month</li>"
            f"<li>{rows} max rows</li>"
            f"<li>{fmts}</li>"
            f"<li>PDF reports: {'✓' if cfg['audit_pdf'] else '✗'}</li>"
            f"<li>API access: {'✓' if cfg['api_access'] else '✗'}</li>"
            f"</ul></div>",
            unsafe_allow_html=True,
        )
