from __future__ import annotations

import math
import re
from typing import Any, Dict, List

import pandas as pd

from .mappings import (
    INT_COLUMNS,
    LIST_COLUMNS,
    SCALAR_STR_COLUMNS,
    SCHEMA,
)
from .transforms import BUILDERS, CASTS, _as_list, _as_str, _is_null


# --------------------------------------------------------------------------- #
#  RECORD-LEVEL ENGINE                                                        #
# --------------------------------------------------------------------------- #

def _resolve_src(record: Dict[str, Any], src: Any) -> Any:
    """Resolve a ``src`` recipe — either a column name or a list of
    candidate column names (first non-empty wins)."""
    if isinstance(src, (list, tuple)):
        for k in src:
            v = record.get(k)
            if not _is_null(v):
                return v
        return None
    return record.get(src)


def _split_value(v: Any, sep: Any) -> List[str]:
    """Split a raw string into list of tokens. ``sep`` may be a single
    delimiter or a list of candidate delimiters (highest-arity split wins)."""
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if not _is_null(x)]
    s = _as_str(v)
    if not s:
        return []
    if isinstance(sep, (list, tuple)):
        best: List[str] = [s]
        for cand in sep:
            parts = s.split(cand)
            if len(parts) > len(best):
                best = parts
        return [p.strip() for p in best if p.strip()]
    parts = s.split(sep)
    return [p.strip() for p in parts if p.strip()]


def _apply_recipe(record: Dict[str, Any], tag: str, recipe: Dict[str, Any]) -> Any:
    """Resolve a single (tag, recipe) pair against one raw record."""
    # 1. Full-record builder — bypass everything else.
    if "builder" in recipe:
        fn = BUILDERS.get(recipe["builder"])
        if fn is None:
            raise KeyError(f"Unknown builder '{recipe['builder']}' (tag={tag}).")
        return fn(record)

    target_type = SCHEMA[tag]["type"]

    # 2. Resolve raw value.
    raw = _resolve_src(record, recipe.get("src")) if "src" in recipe else None

    # 3. List-typed targets.
    if target_type == "list" or recipe.get("list"):
        sep = recipe.get("sep", "; ")
        tokens = _split_value(raw, sep)
        cast = CASTS.get(recipe["cast"]) if "cast" in recipe else None
        if cast is not None:
            tokens = [cast(t) for t in tokens]
        # drop empties produced by the cast
        return [t for t in tokens if not _is_null(t)]

    # 4. Scalar / int targets.
    if "cast" in recipe:
        cast = CASTS.get(recipe["cast"])
        if cast is None:
            raise KeyError(f"Unknown cast '{recipe['cast']}' (tag={tag}).")
        return cast(raw)

    if target_type == "int":
        return CASTS["int_or_zero"](raw)
    return _as_str(raw)


# --------------------------------------------------------------------------- #
#  TYPE-CONTRACT ENFORCEMENT                                                  #
# --------------------------------------------------------------------------- #

def _coerce_to_contract(tag: str, value: Any) -> Any:
    """Force ``value`` to obey the schema's declared type.  Guarantees:
    - list columns → ``list[str]`` (never ``None`` / ``NaN``);
    - str columns  → ``str`` (never ``None`` / ``NaN``);
    - int columns  → ``int`` (never ``None`` / ``NaN``).
    """
    target = SCHEMA[tag]["type"]
    if target == "list":
        return [_as_str(x) for x in _as_list(value) if not _is_null(x)]
    if target == "int":
        if isinstance(value, int):
            return value
        return CASTS["int_or_zero"](value)
    # str
    return _as_str(value)


# --------------------------------------------------------------------------- #
#  PUBLIC API                                                                 #
# --------------------------------------------------------------------------- #

def transform(
    records_df: pd.DataFrame,
    mapping: Dict[str, Dict[str, Any]],
    *,
    db_label: str,
) -> pd.DataFrame:
    """Rename + cast a raw-records DataFrame into the unified WoS schema.

    Parameters
    ----------
    records_df : pd.DataFrame
        Output of :func:`.extractors.extract` — columns are source-native.
    mapping : dict
        Mapping dictionary returned by :func:`.mappings.get_mapping`.
    db_label : str
        Value to store in the ``DB`` column (e.g. ``"SCOPUS"``).
    """
    rows: List[Dict[str, Any]] = []
    raw_records: List[Dict[str, Any]] = records_df.to_dict(orient="records")

    for raw in raw_records:
        row: Dict[str, Any] = {}
        # Apply every recipe in the mapping.
        for tag, recipe in mapping.items():
            try:
                row[tag] = _apply_recipe(raw, tag, recipe)
            except Exception as exc:  # never crash on a single bad row
                row[tag] = [] if SCHEMA[tag]["type"] == "list" else (
                    0 if SCHEMA[tag]["type"] == "int" else ""
                )
                # keep a debug breadcrumb under a private key
                row.setdefault("__etl_errors__", []).append(
                    f"{tag}: {type(exc).__name__}: {exc}"
                )
        # Stamp DB.
        row["DB"] = db_label
        # Apply defaults from recipes that only declare `default`.
        for tag, recipe in mapping.items():
            if "default" in recipe and not row.get(tag):
                row[tag] = recipe["default"]
        rows.append(row)

    # Build the DataFrame with the *full* SCHEMA column order (missing
    # columns get filled with the right empty value below).
    df = pd.DataFrame(rows)

    # Ensure every schema column exists.
    for tag, spec in SCHEMA.items():
        if tag not in df.columns:
            if spec["type"] == "list":
                df[tag] = [[] for _ in range(len(df))]
            elif spec["type"] == "int":
                df[tag] = 0
            else:
                df[tag] = ""

    # Enforce the type contract column-by-column.
    for tag in SCHEMA:
        df[tag] = df[tag].apply(lambda v, t=tag: _coerce_to_contract(t, v))

    # Reorder columns: schema first, then any debug column.
    ordered = list(SCHEMA.keys())
    extras = [c for c in df.columns if c not in ordered]
    return df[ordered + extras]
