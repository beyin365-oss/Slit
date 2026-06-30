"""
Authentication page: Login, Register, Change Password.
"""

import re
import streamlit as st
from db.auth_db import login_user, register_user

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_password(pw: str) -> str | None:
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    return None


def auth_page() -> None:
    """Renders the full login/register UI. Sets st.session_state.user on success."""
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='text-align:center;margin-bottom:1.5rem'>"
            "<div style='font-size:3rem'>🔒</div>"
            "<p style='font-size:2rem;font-weight:900;color:#f0a500;margin:0.2rem 0;letter-spacing:-0.02em'>Slit</p>"
            "<p style='color:#7a90b8;font-size:0.88rem'>Enterprise Data Safety &amp; Compliance Platform</p>"
            "<p style='color:#4a5568;font-size:0.75rem;margin-top:0.3rem'>Trusted by AI labs, banks, hospitals, and data centres worldwide</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            _login_form()

        with tab_register:
            _register_form()


def _login_form() -> None:
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email address", placeholder="you@company.com",
                              autocomplete="email")
        password = st.text_input("Password", type="password", placeholder="••••••••",
                                 autocomplete="current-password")
        submitted = st.form_submit_button("Sign In →", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter your email and password.")
            return
        user, msg = login_user(email, password)
        if user:
            st.session_state.user = user
            st.session_state.page = "Dashboard"
            st.rerun()
        else:
            st.error(f"❌ {msg}")


def _register_form() -> None:
    with st.form("register_form", clear_on_submit=False):
        full_name = st.text_input("Full name", placeholder="Amaka Okonkwo")
        email     = st.text_input("Email address", placeholder="amaka@company.com",
                                  autocomplete="email")
        password  = st.text_input("Password", type="password", placeholder="Min 8 characters")
        confirm   = st.text_input("Confirm password", type="password", placeholder="Repeat password")
        agree     = st.checkbox("I agree to the Terms of Service and Privacy Policy")
        submitted = st.form_submit_button("Create Free Account →", use_container_width=True)

    if submitted:
        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        if not _EMAIL_RE.match(email.strip()):
            errors.append("Enter a valid email address.")
        err = _validate_password(password)
        if err:
            errors.append(err)
        if password != confirm:
            errors.append("Passwords do not match.")
        if not agree:
            errors.append("You must agree to the Terms of Service.")

        if errors:
            for e in errors:
                st.error(e)
            return

        ok, msg = register_user(email.strip(), full_name.strip(), password)
        if ok:
            st.success("✅ Account created! Sign in below.")
            user, _ = login_user(email.strip(), password)
            if user:
                st.session_state.user  = user
                st.session_state.page  = "Dashboard"
                st.rerun()
        else:
            st.error(f"❌ {msg}")
