"""
NDPR Redactor — Global configuration: tiers, limits, constants.
"""

from typing import Optional

# ── Tier definitions ──────────────────────────────────────────────────────────
TIERS: dict[str, dict] = {
    "free": {
        "name":               "Free",
        "price_ngn":          0,
        "price_label":        "₦0 / month",
        "max_files_month":    5,
        "max_rows":           5_000,
        "allowed_formats":    ["csv"],
        "audit_pdf":          False,
        "max_presets":        3,
        "file_history":       5,
        "api_access":         False,
        "priority_support":   False,
        "team_seats":         1,
        "batch_processing":   False,
        "custom_rules":       False,
        "dedicated_sla":      False,
        "white_label":        False,
        "description":        "Get started with essential redaction tools",
        "badge_colour":       "#6b7280",
        "features": [
            "5 file uploads / month",
            "Up to 5,000 rows per file",
            "CSV format only",
            "Basic redaction: Mask & Remove",
            "3 saved presets",
            "5-entry file history",
            "Community support",
        ],
    },
    "basic": {
        "name":               "Basic",
        "price_ngn":          7900,
        "price_label":        "₦7,900 / month",
        "max_files_month":    30,
        "max_rows":           100_000,
        "allowed_formats":    ["csv", "excel"],
        "audit_pdf":          True,
        "max_presets":        15,
        "file_history":       30,
        "api_access":         False,
        "priority_support":   False,
        "team_seats":         1,
        "batch_processing":   False,
        "custom_rules":       False,
        "dedicated_sla":      False,
        "white_label":        False,
        "description":        "For freelancers, SMEs, and small clinics",
        "badge_colour":       "#2563eb",
        "features": [
            "30 file uploads / month",
            "Up to 100,000 rows per file",
            "CSV + Excel formats",
            "All redaction methods (Hash, Pseudonymize, Mask, Remove, Regex)",
            "PDF compliance reports",
            "15 saved presets",
            "30-entry file history",
            "Email support (48h response)",
        ],
    },
    "pro": {
        "name":               "Pro",
        "price_ngn":          15500,
        "price_label":        "₦15,500 / month",
        "max_files_month":    200,
        "max_rows":           1_000_000,
        "allowed_formats":    ["csv", "excel", "json"],
        "audit_pdf":          True,
        "max_presets":        50,
        "file_history":       100,
        "api_access":         True,
        "priority_support":   True,
        "team_seats":         5,
        "batch_processing":   True,
        "custom_rules":       True,
        "dedicated_sla":      False,
        "white_label":        False,
        "description":        "For fintechs, hospitals, and data centres",
        "badge_colour":       "#f0a500",
        "features": [
            "200 file uploads / month",
            "Up to 1,000,000 rows per file",
            "CSV + Excel + JSON formats",
            "All redaction methods + Custom Regex rules",
            "PDF compliance reports + NDPA audit trail",
            "50 saved presets",
            "100-entry file history",
            "REST API access + API key",
            "Up to 5 team seats",
            "Priority support (24h response)",
        ],
    },
    "elite": {
        "name":               "Elite",
        "price_ngn":          36700,
        "price_label":        "₦36,700 / month",
        "max_files_month":    None,      # unlimited
        "max_rows":           None,      # unlimited
        "allowed_formats":    ["csv", "excel", "json"],
        "audit_pdf":          True,
        "max_presets":        None,      # unlimited
        "file_history":       None,      # unlimited
        "api_access":         True,
        "priority_support":   True,
        "team_seats":         None,      # unlimited
        "batch_processing":   True,
        "custom_rules":       True,
        "dedicated_sla":      True,
        "white_label":        True,
        "description":        "For banks, AI labs, and enterprise data operations",
        "badge_colour":       "#7c3aed",
        "features": [
            "Unlimited file uploads",
            "Unlimited rows per file",
            "All formats: CSV, Excel, JSON",
            "All redaction methods + Custom enterprise rules",
            "Full audit suite with branded PDF compliance reports",
            "Unlimited presets",
            "Full file history",
            "Full API access + dedicated API keys",
            "Unlimited team seats",
            "Dedicated account manager + 4-hour SLA",
            "White-label branding option",
            "On-premise deployment support",
        ],
    },
}

# ── Format labels ─────────────────────────────────────────────────────────────
FORMAT_LABELS = {"csv": "CSV", "excel": "Excel (.xlsx/.xls)", "json": "JSON"}

# ── Redaction methods ─────────────────────────────────────────────────────────
METHODS = {
    "hash":         "SHA-256 Hash",
    "pseudonymize": "Pseudonymize",
    "mask":         "Smart Mask",
    "remove":       "Remove Column",
    "regex":        "Custom Regex",
}
METHOD_ICONS = {
    "hash": "🔒", "pseudonymize": "🎭", "mask": "🙈",
    "remove": "🗑️", "regex": "🔧",
}

# ── Security ──────────────────────────────────────────────────────────────────
PBKDF2_ITERATIONS = 260_000     # OWASP recommended 2024
MAX_FILE_SIZE_MB  = 50
DB_PATH           = "ndpr_redactor.db"

# ── Paystack ──────────────────────────────────────────────────────────────────
PAYSTACK_PUBLIC_KEY_ENV  = "PAYSTACK_PUBLIC_KEY"
PAYSTACK_SECRET_KEY_ENV  = "PAYSTACK_SECRET_KEY"
PAYSTACK_CALLBACK_PATH   = "/payment/callback"   # shown to user, not a real route

# ── Helpers ───────────────────────────────────────────────────────────────────

def tier_config(tier: str) -> dict:
    return TIERS.get(tier, TIERS["free"])


def can_upload(tier: str, files_this_month: int) -> tuple[bool, str]:
    cfg = tier_config(tier)
    limit = cfg["max_files_month"]
    if limit is None:
        return True, ""
    if files_this_month >= limit:
        return False, (
            f"You have reached your monthly upload limit of **{limit} files** on the "
            f"**{cfg['name']}** plan. Upgrade to continue."
        )
    return True, ""


def can_process_rows(tier: str, n_rows: int) -> tuple[bool, str]:
    cfg = tier_config(tier)
    limit = cfg["max_rows"]
    if limit is None:
        return True, ""
    if n_rows > limit:
        return False, (
            f"This file has **{n_rows:,} rows**, but the **{cfg['name']}** plan "
            f"supports up to **{limit:,} rows**. Upgrade or split the file."
        )
    return True, ""


def can_use_format(tier: str, fmt: str) -> tuple[bool, str]:
    cfg = tier_config(tier)
    if fmt not in cfg["allowed_formats"]:
        return False, (
            f"The **{cfg['name']}** plan only supports "
            f"{', '.join(FORMAT_LABELS[f] for f in cfg['allowed_formats'])}. "
            f"Upgrade to use {FORMAT_LABELS.get(fmt, fmt)}."
        )
    return True, ""
