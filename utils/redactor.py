"""
Data redaction engine.
Supports: SHA-256 hash, pseudonymization (faker), masking, column removal, custom regex.
Ensures consistency: same input → same output within a session.
"""

import hashlib
import re
import pandas as pd
from typing import Any, Dict, Tuple
from faker import Faker

# Faker instance with Nigerian locale
fake_en = Faker("en_US")
fake_ng = Faker(["en_NG", "en_US"])

# Cache to ensure same input → same fake value
_pseudo_cache: Dict[str, str] = {}


def _hash_value(value: str) -> str:
    """SHA-256 hash — irreversible."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _get_seeded_fake(value: str, field_type: str) -> str:
    """Generate a consistent fake value for the same input using seeded faker."""
    cache_key = f"{field_type}:{value}"
    if cache_key in _pseudo_cache:
        return _pseudo_cache[cache_key]

    seed = int(hashlib.md5(str(value).encode()).hexdigest()[:8], 16)
    fake = Faker("en_US")
    Faker.seed(seed)

    t = field_type
    if t == "phone_number":
        # Nigerian phone format
        prefixes = ["0803", "0805", "0806", "0808", "0810", "0811", "0813",
                    "0814", "0815", "0816", "0817", "0818", "0901", "0903"]
        prefix = prefixes[seed % len(prefixes)]
        suffix = str(seed % 10000000).zfill(7)
        result = f"{prefix}{suffix}"
    elif t == "email":
        result = fake.email()
    elif t == "full_name":
        result = fake.name()
    elif t == "address":
        result = fake.address().replace("\n", ", ")
    elif t == "account_number":
        result = str(seed % 10**10).zfill(10)
    elif t == "bvn":
        result = "2" + str(seed % 10**10).zfill(10)
    elif t == "nin":
        result = str(seed % 10**11).zfill(11)
    elif t == "ip_address":
        octets = [(seed >> (i * 8)) & 0xFF for i in range(4)]
        result = ".".join(str(o) for o in octets)
    elif t == "credit_card":
        result = fake.credit_card_number()
    elif t == "date_of_birth":
        result = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%Y-%m-%d")
    elif t == "bank_details":
        result = fake.bban()
    else:
        result = fake.bothify(text="??######??")

    _pseudo_cache[cache_key] = result
    return result


def _mask_value(value: str, field_type: str) -> str:
    """Apply contextual masking based on field type."""
    s = str(value).strip()

    if field_type == "phone_number":
        if len(s) >= 8:
            return s[:4] + "****" + s[-4:]
        return "****" + s[-3:]

    elif field_type == "email":
        at = s.find("@")
        if at > 1:
            return s[0] + "*" * (at - 1) + s[at:]
        return "****@" + s.split("@")[-1] if "@" in s else "****"

    elif field_type in ("account_number", "nuban"):
        if len(s) >= 6:
            return "*" * (len(s) - 4) + s[-4:]
        return "****"

    elif field_type in ("bvn", "nin"):
        if len(s) >= 5:
            return s[:2] + "*" * (len(s) - 4) + s[-2:]
        return "****"

    elif field_type == "credit_card":
        digits = re.sub(r"\D", "", s)
        if len(digits) >= 8:
            return "*" * (len(digits) - 4) + digits[-4:]
        return "****"

    elif field_type == "ip_address":
        parts = s.split(".")
        if len(parts) == 4:
            return parts[0] + ".*.*." + parts[-1]
        return "***.***.***"

    else:
        # Generic: show first 2 and last 2
        if len(s) > 6:
            return s[:2] + "*" * (len(s) - 4) + s[-2:]
        elif len(s) > 2:
            return s[0] + "*" * (len(s) - 1)
        return "**"


def _validate_regex(pattern: str) -> str | None:
    """
    Validate a user-supplied regex pattern.
    Returns an error message string, or None if the pattern is safe.
    """
    if not pattern:
        return "Pattern is empty."
    if len(pattern) > 500:
        return "Pattern exceeds 500-character limit."
    # Reject common catastrophic-backtracking constructs
    _danger = re.compile(r"(\(.*\+\)\+|\(.*\*\)\*|\(.*\+\)\*|\(\?\:.*\)\{[0-9]+,\})")
    if _danger.search(pattern):
        return "Pattern contains a potentially unsafe construct. Simplify the expression."
    try:
        re.compile(pattern)
    except re.error as e:
        return f"Invalid regex: {e}"
    return None


def _apply_regex(value: str, pattern: str, replacement: str) -> str:
    """Apply custom regex replacement with safety guard."""
    if not pattern:
        return value
    try:
        # Limit execution time via finite input slicing (no timeout primitive in stdlib)
        v = str(value)[:2000]
        return re.sub(pattern, replacement or "[REDACTED]", v, count=50)
    except re.error:
        return str(value)


def clear_pseudo_cache():
    """Clear the pseudonymization cache (call between sessions if needed)."""
    global _pseudo_cache
    _pseudo_cache = {}


class DataRedactor:
    """
    Apply redaction to a DataFrame according to a column configuration.

    config format:
    {
        "column_name": {
            "enabled": True,
            "method": "hash" | "pseudonymize" | "mask" | "remove" | "regex",
            "field_type": "phone_number" | "email" | ...,
            "regex_pattern": str (for method="regex"),
            "regex_replacement": str (for method="regex"),
        }
    }
    """

    def redact(
        self,
        df: pd.DataFrame,
        config: Dict[str, dict],
        progress_callback=None,
    ) -> Tuple[pd.DataFrame, Dict[str, dict]]:
        """
        Redact a DataFrame in place (copy).
        Returns (redacted_df, stats).
        stats: {col: {method, count, field_type}}
        """
        result = df.copy()
        stats = {}

        active_cols = {col: cfg for col, cfg in config.items() if cfg.get("enabled") and col in result.columns}
        total = len(active_cols)

        for i, (col, cfg) in enumerate(active_cols.items()):
            method = cfg.get("method", "mask")
            field_type = cfg.get("field_type", "generic")
            regex_pattern = cfg.get("regex_pattern", "")
            regex_replacement = cfg.get("regex_replacement", "[REDACTED]")

            if method == "remove":
                result.drop(columns=[col], inplace=True)
                stats[col] = {"method": "remove", "count": len(df[col].dropna()), "field_type": field_type}
            else:
                count = 0
                def redact_cell(val, m=method, ft=field_type, rp=regex_pattern, rr=regex_replacement):
                    nonlocal count
                    if pd.isna(val) or str(val).strip() == "":
                        return val
                    v = str(val).strip()
                    count += 1
                    if m == "hash":
                        return _hash_value(v)
                    elif m == "pseudonymize":
                        return _get_seeded_fake(v, ft)
                    elif m == "mask":
                        return _mask_value(v, ft)
                    elif m == "regex":
                        return _apply_regex(v, rp, rr)
                    return v

                result[col] = result[col].apply(redact_cell)
                stats[col] = {"method": method, "count": count, "field_type": field_type}

            if progress_callback:
                progress_callback((i + 1) / total)

        return result, stats
