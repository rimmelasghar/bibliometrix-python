from __future__ import annotations

import math
from typing import Any, Dict, List

import pandas as pd

from .mappings import (
    INT_COLUMNS,
    LIST_COLUMNS,
    MANDATORY_COLUMNS,
    SCALAR_STR_COLUMNS,
    SCHEMA,
)


class ValidationError(ValueError):
    """Raised when the standardised DataFrame violates the target schema."""


def _is_nan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)


def validate(df: pd.DataFrame, *, strict: bool = True) -> Dict[str, Any]:
    """Validate a standardised DataFrame against the schema."""
    report: Dict[str, Any] = {
        "ok": True,
        "missing_mandatory": [],
        "null_columns": [],
        "wrong_type": {},
        "n_records": len(df),
    }

    # (1) mandatory columns
    missing = [c for c in MANDATORY_COLUMNS if c not in df.columns]
    if missing:
        report["ok"] = False
        report["missing_mandatory"] = missing

    # (2) null check + (3-5) type checks
    for tag, spec in SCHEMA.items():
        if tag not in df.columns:
            continue
        col = df[tag]

        # null check (None / NaN). Empty string / [] / 0 are valid placeholders.
        nulls = col.apply(lambda v: v is None or _is_nan(v))
        if nulls.any():
            report["ok"] = False
            report["null_columns"].append(tag)

        # type check (sampled per cell)
        if spec["type"] == "list":
            bad = col.apply(lambda v: not isinstance(v, list))
        elif spec["type"] == "int":
            bad = col.apply(lambda v: not isinstance(v, int) or isinstance(v, bool))
        else:  # str
            bad = col.apply(lambda v: not isinstance(v, str))

        if bad.any():
            report["ok"] = False
            report["wrong_type"][tag] = int(bad.sum())

    if strict and not report["ok"]:
        raise ValidationError(_format_report(report))
    return report


def _format_report(report: Dict[str, Any]) -> str:
    lines = ["Standardised DataFrame failed validation:"]
    if report["missing_mandatory"]:
        lines.append(f"  - missing mandatory columns: {report['missing_mandatory']}")
    if report["null_columns"]:
        lines.append(f"  - columns containing NaN/None: {report['null_columns']}")
    if report["wrong_type"]:
        items = ", ".join(f"{k}({v} cells)" for k, v in report["wrong_type"].items())
        lines.append(f"  - columns with wrong cell type: {items}")
    return "\n".join(lines)
