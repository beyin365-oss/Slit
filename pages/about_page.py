"""
About NDPR — compliance info, privacy policy, terms of service, contact.
"""

import streamlit as st
from config import MAX_FILE_SIZE_MB


def about_page() -> None:
    st.markdown(
        "<div class='page-header'>"
        "<p class='page-title'>About & Compliance</p>"
        "<p class='page-sub'>NDPR / NDPA 2023 information, Privacy Policy, Terms of Service.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    tab_ndpr, tab_privacy, tab_terms, tab_contact = st.tabs([
        "🛡️ NDPA 2023", "🔒 Privacy Policy", "📄 Terms of Service", "📬 Contact Us"
    ])

    with tab_ndpr:
        cl, cr = st.columns([3, 2])
        with cl:
            st.markdown(
                """<div class='card-gold'>
                <h4 style='margin:0 0 0.5rem'>🇳🇬 Nigeria Data Protection Act (NDPA) 2023</h4>
                <p style='margin:0;line-height:1.8;color:#7a90b8'>
                Signed into law in June 2023, the NDPA establishes Nigeria's comprehensive
                data protection framework. It creates the <b style='color:#e8edf8'>Nigeria
                Data Protection Commission (NDPC)</b> and aligns Nigeria with global privacy
                standards (GDPR-inspired).
                </p></div>""", unsafe_allow_html=True)

            st.markdown(
                """<div class='card'>
                <h4 style='margin:0 0 0.7rem'>📌 Key NDPA 2023 Principles</h4>
                <ul style='line-height:2.2;margin:0;padding-left:1.2rem'>
                  <li><b>Lawfulness & Transparency</b> — legal basis required for all processing</li>
                  <li><b>Purpose Limitation</b> — data used only for stated purposes</li>
                  <li><b>Data Minimisation</b> — collect only what is strictly necessary</li>
                  <li><b>Accuracy</b> — personal data kept up to date</li>
                  <li><b>Storage Limitation</b> — retain only as long as needed</li>
                  <li><b>Integrity & Confidentiality</b> — security measures mandatory</li>
                  <li><b>Accountability</b> — demonstrate compliance at all times</li>
                </ul></div>""", unsafe_allow_html=True)

            st.markdown(
                """<div class='card'>
                <h4 style='margin:0 0 0.7rem'>🔐 How Redaction Supports Compliance</h4>
                <table style='width:100%;font-size:0.85rem;border-collapse:collapse'>
                  <tr style='border-bottom:1px solid #1e3560'>
                    <th style='text-align:left;padding:5px'>Technique</th>
                    <th style='text-align:left;padding:5px'>NDPA Principle</th>
                    <th style='text-align:left;padding:5px'>Use case</th>
                  </tr>
                  <tr><td style='padding:5px'>SHA-256 Hash</td><td>Data Minimisation</td><td>Irreversible anonymisation</td></tr>
                  <tr><td style='padding:5px'>Pseudonymise</td><td>Storage Limitation</td><td>Safe test environments</td></tr>
                  <tr><td style='padding:5px'>Mask</td><td>Confidentiality</td><td>Display redaction</td></tr>
                  <tr><td style='padding:5px'>Remove</td><td>Purpose Limitation</td><td>Strip unnecessary fields</td></tr>
                </table></div>""", unsafe_allow_html=True)

        with cr:
            st.markdown(
                """<div class='card'>
                <h4 style='margin:0 0 0.6rem'>🔍 PII Types Detected</h4>
                <ul style='line-height:2.1;font-size:0.85rem;margin:0;padding-left:1.2rem'>
                  <li>📞 Phone numbers (Nigerian &amp; intl)</li>
                  <li>📧 Email addresses</li>
                  <li>👤 Full names</li>
                  <li>🏠 Physical addresses</li>
                  <li>🏦 Bank accounts (NUBAN)</li>
                  <li>🪪 BVN (11-digit)</li>
                  <li>🪪 NIN (National ID)</li>
                  <li>💳 Credit/debit cards</li>
                  <li>🌐 IP addresses (v4/v6)</li>
                  <li>📅 Dates of birth</li>
                  <li>🔑 Passwords &amp; tokens</li>
                  <li>🏛️ IBAN, SWIFT, sort codes</li>
                </ul></div>""", unsafe_allow_html=True)

            st.markdown(
                f"""<div class='card-blue'>
                <h4 style='margin:0 0 0.5rem'>⚙️ Platform Info</h4>
                <table style='font-size:0.83rem;width:100%'>
                  <tr><td><b>Product</b></td><td>Slit</td></tr>
                  <tr><td><b>Version</b></td><td>2.0 Enterprise</td></tr>
                  <tr><td><b>Python</b></td><td>3.13+</td></tr>
                  <tr><td><b>Framework</b></td><td>Streamlit 1.58</td></tr>
                  <tr><td><b>Database</b></td><td>SQLite (WAL mode)</td></tr>
                  <tr><td><b>Max file size</b></td><td>{MAX_FILE_SIZE_MB} MB</td></tr>
                  <tr><td><b>Hash algorithm</b></td><td>SHA-256 (FIPS 180-4)</td></tr>
                  <tr><td><b>Payments</b></td><td>Paystack (Nigeria)</td></tr>
                </table></div>""", unsafe_allow_html=True)

    with tab_privacy:
        st.markdown(
            """<div class='card'>
            <h4>Privacy Policy — NDPR Redactor</h4>
            <p style='color:#7a90b8;font-size:0.82rem'>Last updated: June 2025</p>
            <h5>1. Data We Collect</h5>
            <p>We collect your email address, full name, and hashed password for account management.
            We do <b>not</b> store, retain, or inspect the files you upload for redaction.
            File content exists only in server memory during processing and is discarded immediately after.</p>
            <h5>2. Usage Data</h5>
            <p>We track the number of files and rows processed per month for quota enforcement.
            We record audit metadata (filename, row counts, redaction methods) — never file contents.</p>
            <h5>3. Payment Data</h5>
            <p>Payments are processed by <b>Paystack</b>. We store only the payment reference number.
            We never store card details, bank account numbers, or payment credentials.</p>
            <h5>4. Data Retention</h5>
            <p>Account data is retained until you delete your account.
            Audit log metadata is retained for 12 months. Usage counters are retained for 24 months.</p>
            <h5>5. Your Rights (NDPA 2023)</h5>
            <p>You have the right to access, correct, port, and erase your personal data.
            Contact us at <b>privacy@ndpr-redactor.ng</b> to exercise these rights.</p>
            <h5>6. Security</h5>
            <p>Passwords are stored using PBKDF2-HMAC-SHA256 with 260,000 iterations.
            All communications use HTTPS/TLS. The database uses WAL mode for integrity.</p>
            </div>""", unsafe_allow_html=True)

    with tab_terms:
        st.markdown(
            """<div class='card'>
            <h4>Terms of Service — NDPR Redactor</h4>
            <p style='color:#7a90b8;font-size:0.82rem'>Last updated: June 2025</p>
            <h5>1. Acceptance</h5>
            <p>By using NDPR Redactor, you agree to these terms. If you do not agree, do not use the service.</p>
            <h5>2. Permitted Use</h5>
            <p>This tool is provided for lawful data anonymisation and NDPA/NDPR compliance purposes.
            You must not use it to process data you are not authorised to handle.</p>
            <h5>3. Subscription & Billing</h5>
            <p>Paid plans are billed monthly via Paystack. Cancellation takes effect at the end of the
            current billing period and downgrades the account to the Free plan.</p>
            <h5>4. Limitations</h5>
            <p>We do not guarantee 100% PII detection accuracy. You are responsible for reviewing
            redaction results before use. Hashed values are irreversible — we cannot restore original data.</p>
            <h5>5. Disclaimer</h5>
            <p>This tool supports data minimisation compliance but does not constitute legal advice.
            For sensitive production deployments, consult a qualified data protection officer.</p>
            <h5>6. Governing Law</h5>
            <p>These terms are governed by the laws of the Federal Republic of Nigeria.</p>
            </div>""", unsafe_allow_html=True)

    with tab_contact:
        st.markdown(
            """<div class='card'>
            <h4>Contact &amp; Support — Slit</h4>
            <p style='color:#7a90b8;font-size:0.84rem;margin-bottom:1rem'>
            Whether you are an AI lab, fintech, hospital, or enterprise data centre —
            our team is ready to help you deploy Slit securely.
            </p>
            <table style='font-size:0.9rem;line-height:2.3;width:100%'>
              <tr><td><b>General enquiries</b></td><td><a href='mailto:hello@slit.ng'>hello@slit.ng</a></td></tr>
              <tr><td><b>Privacy &amp; compliance</b></td><td><a href='mailto:privacy@slit.ng'>privacy@slit.ng</a></td></tr>
              <tr><td><b>Enterprise &amp; partnerships</b></td><td><a href='mailto:enterprise@slit.ng'>enterprise@slit.ng</a></td></tr>
              <tr><td><b>Technical support</b></td><td><a href='mailto:support@slit.ng'>support@slit.ng</a></td></tr>
              <tr><td><b>GitHub</b></td><td><a href='https://github.com/beyin365-oss/Slit' target='_blank'>github.com/beyin365-oss/Slit</a></td></tr>
            </table>
            <p style='color:#7a90b8;font-size:0.83rem;margin-top:1rem'>
            Response time: <b>within 24 hours</b> (business days) for Starter/Pro.
            Enterprise clients receive a dedicated account manager and SLA guarantee.
            </p>
            </div>""", unsafe_allow_html=True)
