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

# Ordered for display
_TIER_ORDER = ["free", "basic", "pro", "elite"]
_TIER_UPGRADES = {
    "free":  ["basic", "pro", "elite"],
    "basic": ["pro", "elite"],
    "pro":   ["elite"],
    "elite": [],
}


def billing_page() -> None:
    user = st.session_state.user
    tier = user["tier"]

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Billing & Subscription</p>"
        "<p class='page-sub'>Manage your plan, upgrade anytime, and view payment history.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    sub = get_subscription(user["id"])
    cfg = tier_config(tier)

    # ── Current plan banner ───────────────────────────────────────────────────
    end_date = (sub.get("end_date") or "")[:10] if sub else ""
    st.markdown(
        f"<div class='card-gold'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center'>"
        f"<div>"
        f"<span style='font-weight:800;font-size:1.05rem'>Current Plan: {cfg['name']}</span>"
        f"&nbsp;&nbsp;<span style='color:#f0a500;font-weight:700'>{cfg['price_label']}</span><br>"
        f"<span style='color:#7a90b8;font-size:0.84rem'>{cfg['description']}</span>"
        f"</div>"
        f"<div style='text-align:right;font-size:0.8rem;color:#7a90b8'>"
        f"{'Renews: ' + end_date if end_date else 'Active'}"
        f"</div></div></div>",
        unsafe_allow_html=True,
    )

    # ── Plan comparison ───────────────────────────────────────────────────────
    st.markdown("### Compare Plans")
    _plan_comparison(tier)

    st.divider()

    # ── Upgrade section ───────────────────────────────────────────────────────
    upgrade_tiers = _TIER_UPGRADES.get(tier, [])

    if not upgrade_tiers:
        st.markdown(
            "<div class='card-blue'>"
            "🏆 You are on the <b>Elite</b> plan — the highest tier.<br>"
            "<span style='color:#7a90b8;font-size:0.85rem'>"
            "Need custom on-premise deployment or a volume discount? "
            "Contact <a href='mailto:enterprise@slit.ng'>enterprise@slit.ng</a>."
            "</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### Upgrade Your Plan")
        upgrade_opts = {t: f"{TIERS[t]['name']} — {TIERS[t]['price_label']}"
                        for t in upgrade_tiers}

        col_sel, col_spacer = st.columns([2, 3])
        with col_sel:
            chosen_label = st.selectbox(
                "Select target plan", list(upgrade_opts.values()),
                label_visibility="collapsed"
            )
        target_tier = next(k for k, v in upgrade_opts.items() if v == chosen_label)
        target_cfg  = TIERS[target_tier]
        target_amt  = tier_amount(target_tier)

        # Show what they gain
        _upgrade_diff(cfg, target_cfg)

        st.markdown("<br>", unsafe_allow_html=True)

        if not is_configured():
            st.markdown(
                "<div class='card-warn'>"
                "⚠️ <b>Demo / Test mode</b> — Paystack keys not configured.<br>"
                "<span style='font-size:0.83rem;color:#7a90b8'>"
                "Set <code>PAYSTACK_SECRET_KEY</code> and <code>PAYSTACK_PUBLIC_KEY</code> "
                "in Replit Secrets to enable live payments. "
                "You can simulate an upgrade below for testing.</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                f"✅ Simulate Upgrade to {target_cfg['name']} (demo)",
                use_container_width=True,
            ):
                set_subscription(user["id"], target_tier, "DEMO-REF", target_amt)
                st.session_state.user["tier"] = target_tier
                st.success(f"✅ Upgraded to **{target_cfg['name']}** (demo mode).")
                st.rerun()

        else:
            # Generate a fresh reference tied to this user + target tier
            if (
                "pending_ref" not in st.session_state
                or st.session_state.get("pending_tier") != target_tier
            ):
                st.session_state.pending_ref  = generate_reference(user["id"], target_tier)
                st.session_state.pending_tier = target_tier

            ref = st.session_state.pending_ref

            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    f"💳 Pay ₦{target_amt:,} with Paystack",
                    use_container_width=True,
                ):
                    result = initialize_transaction(user["email"], target_amt, ref)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.pending_ref = result.get("reference", ref)
                        auth_url = result.get("authorization_url", "")
                        st.link_button(
                            "🔗 Open Paystack Payment", auth_url,
                            use_container_width=True,
                        )
            with c2:
                verify_ref = st.text_input(
                    "Paste payment reference to verify",
                    value=st.session_state.pending_ref or "",
                    placeholder="SLIT-PRO-1-...",
                    label_visibility="collapsed",
                )
                if st.button("✅ Verify Payment", use_container_width=True):
                    result = verify_transaction(verify_ref)
                    if result.get("success"):
                        # ── Security: bind payment to this session's user + tier ──
                        paid_email  = (result.get("email") or "").lower().strip()
                        paid_amount = result.get("amount_ngn", 0)
                        expected_amount = tier_amount(target_tier)

                        if paid_email and paid_email != user["email"].lower():
                            st.error(
                                "❌ This payment was made from a different email address. "
                                "Contact support if you believe this is an error."
                            )
                        elif paid_amount < expected_amount:
                            st.error(
                                f"❌ Payment amount ₦{paid_amount:,} is below the required "
                                f"₦{expected_amount:,} for the {target_cfg['name']} plan."
                            )
                        else:
                            set_subscription(user["id"], target_tier, verify_ref, paid_amount)
                            st.session_state.user["tier"] = target_tier
                            st.session_state.pending_ref  = None
                            st.session_state.pending_tier = None
                            st.success(
                                f"✅ Payment verified! You are now on **{target_cfg['name']}**."
                            )
                            st.rerun()
                    else:
                        st.error(f"❌ {result.get('error', 'Payment not verified.')}")

    # ── Cancel / Downgrade ────────────────────────────────────────────────────
    if tier != "free":
        st.divider()
        with st.expander("⚠️ Cancel Subscription"):
            st.warning(
                "Cancelling will downgrade your account to the **Free** plan immediately. "
                "Your audit log and presets are preserved."
            )
            if st.button("Cancel & Downgrade to Free", type="primary"):
                cancel_subscription(user["id"])
                st.session_state.user["tier"] = "free"
                st.success("Subscription cancelled. You are now on the Free plan.")
                st.rerun()

    # ── Payment history ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Payment History")
    history = subscription_history(user["id"])
    if history:
        import pandas as pd
        rows = [
            {
                "Date":      h["created_at"][:10],
                "Plan":      TIERS.get(h["tier"], {}).get("name", h["tier"]),
                "Status":    h["status"].capitalize(),
                "Amount":    f"₦{h['amount_ngn']:,}" if h.get("amount_ngn") else "—",
                "Reference": (h.get("paystack_ref") or "—")[:30],
            }
            for h in history
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No payment records yet.")


# ── Plan comparison table ─────────────────────────────────────────────────────

def _plan_comparison(current_tier: str) -> None:
    cols = st.columns(4)
    for col, tk in zip(cols, _TIER_ORDER):
        cfg       = TIERS[tk]
        is_cur    = tk == current_tier
        border    = "border:2px solid #f0a500" if is_cur else "border:1px solid #1e3560"
        tclr      = cfg["badge_colour"]
        files_lbl = "∞" if not cfg["max_files_month"] else f"{cfg['max_files_month']}"
        rows_lbl  = "∞" if not cfg["max_rows"]         else f"{cfg['max_rows']:,}"
        seats_lbl = "∞" if not cfg["team_seats"]       else str(cfg["team_seats"])
        fmts      = " · ".join(f.upper() for f in cfg["allowed_formats"])

        features_html = "".join(
            f"<li style='line-height:1.9'>{feat}</li>"
            for feat in cfg.get("features", [])
        )

        col.markdown(
            f"<div class='card' style='{border};position:relative;min-height:420px'>"
            + (
                f"<div style='position:absolute;top:-10px;left:50%;transform:translateX(-50%);"
                f"background:#f0a500;color:#0a1226;padding:2px 14px;border-radius:20px;"
                f"font-size:0.7rem;font-weight:800;white-space:nowrap'>YOUR PLAN</div>"
                if is_cur else ""
            )
            + f"<div style='text-align:center;margin-bottom:0.8rem'>"
            + f"<span style='background:{tclr}22;color:{tclr};border:1px solid {tclr}44;"
            + f"border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:700'>{cfg['name']}</span>"
            + f"</div>"
            + f"<p style='font-size:1.25rem;font-weight:900;margin:0;text-align:center'>{cfg['price_label'].split('/')[0].strip()}</p>"
            + f"<p style='color:#7a90b8;font-size:0.72rem;text-align:center;margin:0 0 0.6rem'>per month</p>"
            + f"<p style='color:#7a90b8;font-size:0.8rem;text-align:center;margin:0 0 0.8rem;min-height:2.4rem'>{cfg['description']}</p>"
            + f"<ul style='font-size:0.79rem;padding-left:1.1rem;margin:0;list-style:none'>"
            + features_html
            + f"</ul></div>",
            unsafe_allow_html=True,
        )


def _upgrade_diff(current_cfg: dict, target_cfg: dict) -> None:
    """Show a concise summary of what the user gains by upgrading."""
    gains = []

    c_files = current_cfg["max_files_month"]
    t_files = target_cfg["max_files_month"]
    if t_files is None:
        gains.append("Unlimited file uploads (vs "
                     f"{'∞' if c_files is None else str(c_files) + '/mo'})")
    elif c_files is None or t_files > c_files:
        gains.append(f"Up to **{t_files}/mo** uploads")

    c_rows = current_cfg["max_rows"]
    t_rows = target_cfg["max_rows"]
    if t_rows is None:
        gains.append("Unlimited rows per file")
    elif c_rows is None or t_rows > c_rows:
        gains.append(f"Up to **{t_rows:,}** rows per file")

    new_fmts = set(target_cfg["allowed_formats"]) - set(current_cfg["allowed_formats"])
    if new_fmts:
        gains.append(f"New format support: {', '.join(f.upper() for f in new_fmts)}")

    if not current_cfg["audit_pdf"] and target_cfg["audit_pdf"]:
        gains.append("PDF compliance report generation")

    if not current_cfg["api_access"] and target_cfg["api_access"]:
        gains.append("REST API access + API key")

    if not current_cfg["priority_support"] and target_cfg["priority_support"]:
        gains.append("Priority support (24h response)")

    if not current_cfg.get("dedicated_sla") and target_cfg.get("dedicated_sla"):
        gains.append("Dedicated account manager + 4-hour SLA")

    if not current_cfg.get("white_label") and target_cfg.get("white_label"):
        gains.append("White-label branding")

    c_seats = current_cfg.get("team_seats", 1)
    t_seats = target_cfg.get("team_seats")
    if t_seats is None:
        gains.append("Unlimited team seats")
    elif c_seats is None or (t_seats and t_seats > (c_seats or 0)):
        gains.append(f"Up to **{t_seats}** team seats")

    if not gains:
        return

    items = "".join(f"<li>✓ {g}</li>" for g in gains)
    st.markdown(
        f"<div class='card-blue'>"
        f"<b>What you gain with {target_cfg['name']}:</b>"
        f"<ul style='margin:0.5rem 0 0;padding-left:1.4rem;font-size:0.86rem;line-height:2'>"
        f"{items}</ul></div>",
        unsafe_allow_html=True,
    )
