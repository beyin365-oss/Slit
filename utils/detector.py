"""
Sensitive data auto-detection module.
Detects PII and sensitive fields by column name patterns and value analysis.
"""

import re
import pandas as pd
from typing import Dict, Tuple

# ─── Regex patterns for value-level detection ─────────────────────────────────

PATTERNS = {
    "phone_number": [
        re.compile(r"^(\+234|0)(7[0-9]|8[0-9]|9[0-9])\d{8}$"),          # Nigerian mobile
        re.compile(r"^\+?1?\s*[-.]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$"),  # International
        re.compile(r"^\d{10,15}$"),                                          # Generic numeric
    ],
    "email": [
        re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"),
    ],
    "account_number": [
        re.compile(r"^\d{10}$"),   # Nigerian 10-digit account
        re.compile(r"^\d{8,18}$"), # General bank account
    ],
    "bvn": [
        re.compile(r"^2\d{10}$"),  # BVN: 11 digits starting with 2
    ],
    "nin": [
        re.compile(r"^\d{11}$"),   # NIN: 11 digits
    ],
    "ip_address": [
        re.compile(r"^\d{1,3}(\.\d{1,3}){3}$"),   # IPv4
        re.compile(r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"),  # IPv6
    ],
    "credit_card": [
        re.compile(r"^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$"),
    ],
    "date_of_birth": [
        re.compile(r"^\d{2}[/\-]\d{2}[/\-]\d{4}$"),
        re.compile(r"^\d{4}[/\-]\d{2}[/\-]\d{2}$"),
    ],
}

# ─── Column name keyword hints ────────────────────────────────────────────────

COLUMN_HINTS: Dict[str, Tuple[str, float]] = {
    # phone
    "phone": ("phone_number", 0.95),
    "mobile": ("phone_number", 0.95),
    "tel": ("phone_number", 0.90),
    "telephone": ("phone_number", 0.95),
    "gsm": ("phone_number", 0.95),
    "cell": ("phone_number", 0.90),
    # email
    "email": ("email", 0.98),
    "e_mail": ("email", 0.98),
    "mail": ("email", 0.85),
    # name
    "name": ("full_name", 0.90),
    "fullname": ("full_name", 0.95),
    "full_name": ("full_name", 0.95),
    "firstname": ("full_name", 0.90),
    "first_name": ("full_name", 0.90),
    "lastname": ("full_name", 0.90),
    "last_name": ("full_name", 0.90),
    "surname": ("full_name", 0.90),
    "customer_name": ("full_name", 0.95),
    # address
    "address": ("address", 0.95),
    "street": ("address", 0.90),
    "city": ("address", 0.75),
    "state": ("address", 0.70),
    "location": ("address", 0.80),
    "residence": ("address", 0.85),
    "home_address": ("address", 0.95),
    # account number
    "account": ("account_number", 0.85),
    "account_no": ("account_number", 0.95),
    "account_number": ("account_number", 0.98),
    "acct": ("account_number", 0.85),
    "nuban": ("account_number", 0.98),
    # BVN
    "bvn": ("bvn", 0.99),
    "bank_verification": ("bvn", 0.99),
    # NIN
    "nin": ("nin", 0.99),
    "national_id": ("nin", 0.98),
    "national_identification": ("nin", 0.98),
    # bank details
    "bank": ("bank_details", 0.80),
    "bank_name": ("bank_details", 0.90),
    "sort_code": ("bank_details", 0.95),
    "iban": ("bank_details", 0.99),
    "swift": ("bank_details", 0.95),
    "routing": ("bank_details", 0.90),
    # IP
    "ip": ("ip_address", 0.90),
    "ip_address": ("ip_address", 0.99),
    "ipv4": ("ip_address", 0.99),
    # Credit card
    "card": ("credit_card", 0.85),
    "card_number": ("credit_card", 0.99),
    "pan": ("credit_card", 0.99),
    # Date of birth
    "dob": ("date_of_birth", 0.99),
    "date_of_birth": ("date_of_birth", 0.99),
    "birth_date": ("date_of_birth", 0.99),
    "birthday": ("date_of_birth", 0.95),
    # Password / token
    "password": ("password", 0.99),
    "passwd": ("password", 0.99),
    "secret": ("password", 0.95),
    "token": ("password", 0.90),
    "pin": ("password", 0.90),
    "ssn": ("nin", 0.95),
    "ssn_number": ("nin", 0.99),
    # gender / personal
    "gender": ("personal_info", 0.70),
    "sex": ("personal_info", 0.70),
    "nationality": ("personal_info", 0.70),
    "religion": ("personal_info", 0.80),
}

# Human-readable type labels
TYPE_LABELS = {
    "phone_number": "Phone Number",
    "email": "Email Address",
    "full_name": "Full Name",
    "address": "Physical Address",
    "account_number": "Account Number",
    "bvn": "Bank Verification Number (BVN)",
    "nin": "National Identification Number (NIN)",
    "bank_details": "Bank Details",
    "ip_address": "IP Address",
    "credit_card": "Credit/Debit Card Number",
    "date_of_birth": "Date of Birth",
    "password": "Password / Secret Token",
    "personal_info": "Personal Information",
}


class SensitiveDataDetector:
    """Detects sensitive/PII columns in a DataFrame."""

    def detect(self, df: pd.DataFrame, sample_size: int = 200) -> Dict[str, dict]:
        """
        Analyze each column for sensitive data.
        Returns dict: {col_name: {type, label, confidence, sample_count, match_count}}
        """
        results = {}

        for col in df.columns:
            detection = self._detect_column(df[col], col, sample_size)
            if detection:
                results[col] = detection

        return results

    def _detect_column(self, series: pd.Series, col_name: str, sample_size: int) -> dict | None:
        col_lower = col_name.lower().strip().replace(" ", "_").replace("-", "_")

        # 1. Column name hint (highest priority)
        for keyword, (dtype, confidence) in COLUMN_HINTS.items():
            if keyword == col_lower or col_lower.endswith(f"_{keyword}") or col_lower.startswith(f"{keyword}_"):
                return {
                    "type": dtype,
                    "label": TYPE_LABELS.get(dtype, dtype.replace("_", " ").title()),
                    "confidence": confidence,
                    "source": "column_name",
                    "match_count": len(series.dropna()),
                    "sample_count": len(series.dropna()),
                }

        # Partial match fallback
        for keyword, (dtype, base_conf) in COLUMN_HINTS.items():
            if keyword in col_lower:
                confidence = base_conf * 0.85
                return {
                    "type": dtype,
                    "label": TYPE_LABELS.get(dtype, dtype.replace("_", " ").title()),
                    "confidence": round(confidence, 2),
                    "source": "column_name_partial",
                    "match_count": len(series.dropna()),
                    "sample_count": len(series.dropna()),
                }

        # 2. Value-level pattern detection
        sample = series.dropna().astype(str).head(sample_size)
        if len(sample) == 0:
            return None

        best_type = None
        best_confidence = 0.0
        best_matches = 0

        for dtype, pattern_list in PATTERNS.items():
            matches = 0
            for val in sample:
                val_clean = val.strip()
                for pat in pattern_list:
                    if pat.match(val_clean):
                        matches += 1
                        break

            if matches > 0:
                ratio = matches / len(sample)
                if ratio >= 0.3 and ratio > best_confidence:
                    best_confidence = ratio
                    best_type = dtype
                    best_matches = matches

        if best_type and best_confidence >= 0.3:
            return {
                "type": best_type,
                "label": TYPE_LABELS.get(best_type, best_type.replace("_", " ").title()),
                "confidence": round(min(best_confidence * 0.9, 0.97), 2),
                "source": "value_pattern",
                "match_count": best_matches,
                "sample_count": len(sample),
            }

        return None
