"""
Settings: profile, password, presets management, API key.
"""

import secrets
import streamlit as st
from config import tier_config
from db.auth_db import update_password, update_profile
from db.presets_db import list_presets, delete_preset, count_presets


def settings_page() -> None:
    user = st.session_state.user

    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>Settings</p>"
        "<p class='page-sub'>Manage your profile, password, presets, and API access.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    tab_profile, tab_password, tab_presets, tab_api = st.tabs([
        "👤 Profile", "🔑 Password", "💾 Presets", "🔌 API Key"
    ])

    # ── Profile ──────────────────────────────────────────────────────────────
    with tab_profile:
        st.markdown("### Update Profile")
        with st.form("profile_form"):
            new_name = st.text_input("Full name", value=user["full_name"])
            st.text_input("Email", value=user["email"], disabled=True,
                          help="Email cannot be changed. Contact support.")
            if st.form_submit_button("Save Changes", use_container_width=True):
                if new_name.strip():
                    update_profile(user["id"], new_name.strip())
                    st.session_state.user["full_name"] = new_name.strip()
                    st.success("✅ Profile updated.")
                else:
                    st.error("Name cannot be empty.")

    # ── Password ──────────────────────────────────────────────────────────────
    with tab_password:
        st.markdown("### Change Password")
        with st.form("password_form"):
            current = st.text_input("Current password", type="password")
            new_pw  = st.text_input("New password", type="password",
                                    help="Minimum 8 characters")
            confirm = st.text_input("Confirm new password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                from db.auth_db import verify_password, get_user_by_id
                db_user = get_user_by_id(user["id"])
                if not db_user:
                    st.error("User not found.")
                elif not verify_password(current, db_user["password_hash"]):
                    st.error("Current password is incorrect.")
                elif len(new_pw) < 8:
                    st.error("New password must be at least 8 characters.")
                elif new_pw != confirm:
                    st.error("Passwords do not match.")
                else:
                    update_password(user["id"], new_pw)
                    st.success("✅ Password updated successfully.")

    # ── Presets ───────────────────────────────────────────────────────────────
    with tab_presets:
        st.markdown("### Saved Redaction Presets")
        cfg        = tier_config(user["tier"])
        max_p      = cfg["max_presets"]
        presets    = list_presets(user["id"])
        count      = count_presets(user["id"])

        if max_p is not None:
            st.caption(f"{count} / {max_p} presets used")

        if not presets:
            st.info("No presets saved yet. Save your redaction configuration as a preset from the Upload & Redact tab.")
        else:
            for name in presets:
                pc1, pc2, pc3 = st.columns([5, 1, 1])
                with pc1:
                    st.markdown(f"📋 **{name}**")
                with pc2:
                    if st.button("Load", key=f"load_preset_{name}"):
                        from db.presets_db import load_preset
                        config = load_preset(user["id"], name)
                        if config:
                            st.session_state.redact_cfg = config
                            st.session_state.page = "Upload & Redact"
                            st.success(f"Preset '{name}' loaded. Go to Upload & Redact.")
                            st.rerun()
                with pc3:
                    if st.button("Delete", key=f"del_preset_{name}"):
                        delete_preset(user["id"], name)
                        st.rerun()

        if max_p is not None and count >= max_p:
            st.markdown(
                f"<div class='card-warn'>You've reached your preset limit ({max_p}). "
                f"Upgrade to save more presets.</div>",
                unsafe_allow_html=True,
            )

    # ── API Key ───────────────────────────────────────────────────────────────
    with tab_api:
        st.markdown("### API Key")
        if user["tier"] not in ("pro", "enterprise"):
            st.markdown(
                "<div class='card-warn'>"
                "🔌 API access is available on the <b>Pro</b> and <b>Enterprise</b> plans.<br>"
                "<small style='color:#7a90b8'>Upgrade your plan to get API access for automated redaction workflows.</small>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("⬆ Upgrade to Pro", use_container_width=False):
                st.session_state.page = "Billing"
                st.rerun()
        else:
            # Generate/display a session-based API key placeholder
            if "api_key" not in st.session_state:
                st.session_state.api_key = f"ndpr_live_{secrets.token_hex(24)}"

            st.markdown(
                "<div class='card-blue'>"
                "🔌 <b>Your API Key</b> (keep this secret!)<br>"
                "<small style='color:#7a90b8'>Full API documentation available at "
                "<code>/api/docs</code> — contact support for SDK access.</small>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.code(st.session_state.api_key, language=None)
            st.warning("⚠️ This key is session-generated. A persistent API key system requires database integration — contact support.")
            if st.button("🔄 Regenerate Key"):
                st.session_state.api_key = f"ndpr_live_{secrets.token_hex(24)}"
                st.rerun()
