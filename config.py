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
        "description":        "For students and small teams",
        "badge_colour":       "#6b7280",
    },
    "starter": {
        "name":               "Starter",
        "price_ngn":          4900,
        "price_label":        "₦4,900 / month",
        "max_files_month":    50,
        "max_rows":           50_000,
        "allowed_formats":    ["csv", "excel"],
        "audit_pdf":          True,
        "max_presets":        10,
        "file_history":       20,
        "api_access":         False,
        "priority_support":   False,
        "description":        "For freelancers and SMEs",
        "badge_colour":       "#2563eb",
    },
    "pro": {
        "name":               "Pro",
        "price_ngn":          14900,
        "price_label":        "₦14,900 / month",
        "max_files_month":    None,   # unlimited
        "max_rows":           500_000,
        "allowed_formats":    ["csv", "excel", "json"],
        "audit_pdf":          True,
        "max_presets":        None,   # unlimited
        "file_history":       100,
        "api_access":         True,
        "priority_support":   True,
        "description":        "For fintech and data centres",
        "badge_colour":       "#f0a500",
    },
    "enterprise": {
        "name":               "Enterprise",
        "price_ngn":          None,   # custom
        "price_label":        "Custom pricing",
        "max_files_month":    None,
        "max_rows":           None,
        "allowed_formats":    ["csv", "excel", "json"],
        "audit_pdf":          True,
        "max_presets":        None,
        "file_history":       None,
        "api_access":         True,
        "priority_support":   True,
        "description":        "For banks and large data centres",
        "badge_colour":       "#7c3aed",
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
