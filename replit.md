# Slit — Enterprise Data Safety & Compliance Platform

Slit is a production-grade data safety SaaS — trusted by AI labs, banks, hospitals, fintech companies, and data centres. It redacts, masks, hashes, and pseudonymizes PII from CSV, Excel, and JSON files with full NDPA 2023 / NDPR / GDPR-aligned audit trails, tiered subscriptions, and Paystack billing.

## Run & Operate

- `streamlit run app.py --server.port 5000` — start the Streamlit app (workflow: "NDPR Redaction Tool")
- `ACCESS_CODE` env var — access gate password (default behaviour: contact admin)
- Audit logs persist to `audit_logs.json` in the project root

## Stack

- Python 3.13 · Streamlit 1.58
- pandas, openpyxl, xlrd — file parsing
- Faker — pseudonymisation
- fpdf2 — PDF compliance reports
- hashlib (stdlib) — SHA-256 hashing & file integrity

## Where things live

- `app.py` — main Streamlit app (auth gate, CSS, 4-tab UI)
- `utils/detector.py` — regex + column-name PII detection
- `utils/redactor.py` — hash / pseudonymize / mask / remove / regex
- `utils/audit.py` — audit entry creation, JSON persistence, PDF/CSV export
- `utils/file_handler.py` — CSV/Excel/JSON read & write
- `audit_logs.json` — persisted audit log (auto-created on first run)

## Architecture decisions

- Chunked processing (5000 rows/chunk) avoids memory spikes on large files
- Pseudonymisation is seed-deterministic: same input → same fake value within a session
- All regex patterns are validated and capped at 500 chars before use (DoS prevention)
- Audit log is persisted to disk and merged with in-session entries on every render
- Access code is env-var controlled; default is never shown in production UI

## User preferences

- Blue (#2563eb) and gold (#f0a500) colour scheme — clean, professional
- Tabs: Upload & Redact | Preview & Process | Audit Log | About NDPR
- Dark mode default; light mode toggle in sidebar

## Gotchas

- `ACCESS_CODE` env var must be set before deploying publicly
- `audit_logs.json` grows unboundedly — archive or rotate periodically in production
- `xlrd` only supports `.xls` (old Excel); `.xlsx` uses `openpyxl`

## Pointers

- See the `pnpm-workspace` skill for the monorepo's Node/TS structure (API server runs separately)
