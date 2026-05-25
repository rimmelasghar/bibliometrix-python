from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .derived import add_sr
from .extractors import extract
from .mappings import DB_LABELS, get_mapping
from .transformers import transform
from .validator import validate


def convert2df(
    source: str,
    file_path: Optional[str] = None,
    *,
    file_type: Optional[str] = None,
    records: Optional[List[Dict[str, Any]]] = None,
    validate_strict: bool = False,
    db_label: Optional[str] = None,
) -> pd.DataFrame:
    """Convert a raw bibliographic export (or API payload) into the unified
    WoS-style DataFrame used by every analytical function.

    Parameters
    ----------
    source : str
        One of ``wos``, ``scopus``, ``pubmed``, ``dimensions``, ``lens``,
        ``cochrane``, ``openalex``.
    file_path : str, optional
        Path to a raw export file.  Required when ``records`` is not given.
    file_type : str, optional
        Force a specific file-type ("csv", "xlsx", "txt", "ciw", "bib",
        "json").  Auto-detected from ``file_path`` if not supplied.
    records : list[dict], optional
        Pre-fetched raw records (typically from one of the API retrievers
        in :mod:`.api_retriever`).  When supplied the EXTRACT phase is
        skipped and ``file_type`` is forced to ``"json"``.
    validate_strict : bool, default False
        If True, raise :class:`.validator.ValidationError` on contract
        violations.  If False, attach the validation report to the
        DataFrame as ``df.attrs["etl_report"]``.
    db_label : str, optional
        Override the value stored in the ``DB`` column (default comes from
        :data:`.mappings.DB_LABELS`).

    Returns
    -------
    pd.DataFrame
        A DataFrame following the unified WoS schema.  See
        :data:`.mappings.SCHEMA` for the column list and their declared
        Python types.

    Examples
    --------
    >>> df = convert2df("scopus", "sources/Scopus/Scopus.csv")
    >>> df.columns.tolist()[:6]
    ['DB', 'UT', 'DI', 'PMID', 'TI', 'SO']
    >>> df["AU"].iloc[0]  # always a list
    ['Smith J', 'Doe A']
    """
    src = source.lower()

    # ----- Phase 1: EXTRACT --------------------------------------------- #
    records_df, ft = extract(
        source=src,
        file_path=file_path,
        file_type=file_type,
        records=records,
    )

    # ----- Phase 2/3: TRANSFORM (rename + cast + null) ------------------ #
    mapping = get_mapping(src, ft)
    label = db_label or DB_LABELS.get(src, src.upper())
    df = transform(records_df, mapping, db_label=label)

    # ----- Phase 4: DERIVED FIELDS (SR) --------------------------------- #
    raw_records = records_df.to_dict(orient="records")
    df = add_sr(df, source=src, file_type=ft, raw_records=raw_records)

    # ----- Phase 5: VALIDATE -------------------------------------------- #
    report = validate(df, strict=validate_strict)
    df.attrs["etl_report"] = report
    df.attrs["etl_source"] = src
    df.attrs["etl_file_type"] = ft
    return df
