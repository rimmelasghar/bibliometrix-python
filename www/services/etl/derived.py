from __future__ import annotations

import importlib
from typing import Any, Dict

import pandas as pd

_format_sr_column = None


def _load_format_sr():  # pragma: no cover - import guard
    """Import the existing SR helper lazily so the ETL stays usable even
    when the dashboard's heavy dependency stack isn't installed."""
    global _format_sr_column
    if _format_sr_column is not None:
        return _format_sr_column
    try:
        mod = importlib.import_module("www.services.format_functions")
        _format_sr_column = getattr(mod, "format_sr_column", None)
    except Exception:
        _format_sr_column = None
    return _format_sr_column


# --------------------------------------------------------------------------- #
#  PUBLIC API                                                                 #
# --------------------------------------------------------------------------- #

def _generic_sr(row: pd.Series) -> str:
    """Source-agnostic fallback that uses already-standardised columns."""
    au = row.get("AU") or []
    first_author = au[0] if isinstance(au, list) and au else ""
    py = row.get("PY", "")
    py = str(py) if py not in (None, 0, "") else ""
    journal = row.get("JI") or row.get("SO") or ""
    parts = [p for p in (first_author, str(py), str(journal)) if p]
    return ", ".join(parts)


def add_sr(
    df: pd.DataFrame,
    *,
    source: str,
    file_type: str,
    raw_records: list[dict] | None = None,
) -> pd.DataFrame:
    """Add the ``SR`` column to a standardised DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Already-standardised dataframe (post :func:`.transformers.transform`).
    source : str
        Lower-case ETL source identifier.
    file_type : str
        File-type string ("csv", "txt", ...).
    raw_records : list[dict], optional
        The original raw records.  When supplied and the existing
        ``format_sr_column`` helper supports the (source, file_type) pair,
        SR is computed by delegation (assignment requirement).  Otherwise
        the generic fallback is used.
    """
    sr_fn = _load_format_sr()

    # Map ETL source-key → label expected by format_sr_column.
    legacy_source = {
        "wos":        "Web_of_Science",
        "scopus":     "Scopus",
        "pubmed":     "PubMed",
        "dimensions": "Dimensions",
        "lens":       "The_Lens",
        "cochrane":   "Cochrane",
    }.get(source.lower())

    legacy_filetype = "." + file_type.lstrip(".").lower()

    sr_values = []
    use_legacy = (
        sr_fn is not None
        and legacy_source is not None
        and raw_records is not None
        and len(raw_records) == len(df)
    )

    for i, (_, row) in enumerate(df.iterrows()):
        sr = ""
        if use_legacy:
            try:
                sr = sr_fn(raw_records[i], legacy_source, legacy_filetype) or ""
            except Exception:
                sr = ""
        if not sr:
            sr = _generic_sr(row)
        sr_values.append(sr.strip(", "))

    df = df.copy()
    df["SR"] = sr_values
    return df
