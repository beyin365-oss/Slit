"""
File reading and writing utilities.
Supports CSV, Excel (.xlsx/.xls), and JSON formats.
"""

import io
import json
import pandas as pd
from typing import Tuple


MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def detect_format(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "csv":
        return "csv"
    elif ext in ("xlsx", "xls"):
        return "excel"
    elif ext == "json":
        return "json"
    return "unknown"


def read_file(file_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, str]:
    """
    Parse uploaded file bytes into a DataFrame.
    Returns (df, format_string).
    Raises ValueError on unsupported format or any parse error (normalised).
    """
    fmt = detect_format(filename)
    buf = io.BytesIO(file_bytes)

    if fmt == "csv":
        last_err: Exception | None = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                buf.seek(0)
                df = pd.read_csv(buf, encoding=enc, low_memory=False)
                return df, "csv"
            except (UnicodeDecodeError, Exception) as e:
                last_err = e
                continue
        raise ValueError(f"Could not parse CSV file: {last_err}. Try saving as UTF-8.")

    elif fmt == "excel":
        try:
            engine = "openpyxl" if filename.lower().endswith("xlsx") else "xlrd"
            df = pd.read_excel(buf, engine=engine)
            return df, "excel"
        except Exception as e:
            raise ValueError(f"Could not read Excel file: {e}")

    elif fmt == "json":
        try:
            buf.seek(0)
            raw_bytes = buf.read()
            # Try UTF-8 first, fall back to latin-1
            for enc in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    text = raw_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode JSON file — unsupported encoding.")
            raw = json.loads(text)
            if isinstance(raw, list):
                df = pd.DataFrame(raw)
            elif isinstance(raw, dict):
                if any(isinstance(v, list) for v in raw.values()):
                    df = pd.DataFrame(raw)
                else:
                    df = pd.DataFrame([raw])
            else:
                raise ValueError("JSON must be an array of objects or a column-oriented object.")
            return df, "json"
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Could not parse JSON file: {e}")

    else:
        raise ValueError(
            f"Unsupported format: '{filename}'. Upload CSV, Excel (.xlsx/.xls), or JSON."
        )


def write_file(df: pd.DataFrame, fmt: str, original_filename: str) -> Tuple[bytes, str, str]:
    """
    Serialize a DataFrame back to its original format.
    Returns (bytes, mime_type, suggested_filename).
    """
    base = original_filename.rsplit(".", 1)[0] + "_redacted"

    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8"), "text/csv", base + ".csv"

    elif fmt == "excel":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Redacted")
        return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", base + ".xlsx"

    elif fmt == "json":
        data = df.to_json(orient="records", indent=2)
        return data.encode("utf-8"), "application/json", base + ".json"

    else:
        # Fallback to CSV
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8"), "text/csv", base + ".csv"


def file_info(df: pd.DataFrame, filename: str, file_bytes: bytes) -> dict:
    """Return metadata about an uploaded file."""
    size_bytes = len(file_bytes)
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024*1024):.2f} MB"
    elif size_bytes >= 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes} B"

    return {
        "filename": filename,
        "format": detect_format(filename).upper(),
        "size": size_str,
        "size_bytes": size_bytes,
        "rows": len(df),
        "columns": len(df.columns),
        "memory": f"{df.memory_usage(deep=True).sum() / (1024*1024):.2f} MB",
    }
