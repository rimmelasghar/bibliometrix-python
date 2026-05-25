from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import _parsers


# --------------------------------------------------------------------------- #
#  PUBLIC API                                                                 #
# --------------------------------------------------------------------------- #

def extract(
    source: str,
    file_path: Optional[str] = None,
    file_type: Optional[str] = None,
    records: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[pd.DataFrame, str]:
    """Load raw bibliographic data.

    Parameters
    ----------
    source : str
        Lower-case source identifier (``wos``, ``scopus``, ``pubmed``,
        ``dimensions``, ``lens``, ``cochrane``, ``openalex``).
    file_path : str, optional
        Path to a raw export. Required for file-based sources.
    file_type : str, optional
        File extension (without leading dot). Auto-detected from
        ``file_path`` if not supplied.
    records : list[dict], optional
        Already-extracted raw records (e.g. coming from the API
        retrievers).  When supplied, ``file_path``/``file_type`` are
        ignored and ``file_type`` is forced to ``"json"``.

    Returns
    -------
    (records_df, file_type) : tuple
        ``records_df`` — DataFrame whose columns are the *raw, source-native*
        column names.  ``file_type`` — the resolved file-type string used to
        pick the mapping (always ``"json"`` for API records).
    """
    source = source.lower()

    if records is not None:
        return pd.DataFrame(records), "json"

    if not file_path:
        raise ValueError("extract() requires either `file_path` or `records`.")

    ft = (file_type or os.path.splitext(file_path)[1].lstrip(".")).lower()
    loader = _LOADERS.get((source, ft))
    if loader is None:
        raise ValueError(
            f"No extractor registered for source='{source}' file_type='{ft}'. "
            f"Supported pairs: {sorted(_LOADERS.keys())}"
        )
    return loader(file_path), ft


# --------------------------------------------------------------------------- #
#  PER-FORMAT LOADERS                                                         #
# --------------------------------------------------------------------------- #

def _load_csv(path: str, *, skiprows: int = 0) -> pd.DataFrame:
    return pd.read_csv(path, skiprows=skiprows, dtype=object, keep_default_na=False)


def _load_excel(path: str, *, skiprows: int = 0) -> pd.DataFrame:
    return pd.read_excel(path, skiprows=skiprows, dtype=object)


def _load_dimensions_csv(path: str) -> pd.DataFrame:
    # Dimensions exports carry a one-line "About the data" banner on row 1.
    return _load_csv(path, skiprows=1)


def _load_dimensions_xlsx(path: str) -> pd.DataFrame:
    return _load_excel(path, skiprows=1)


def _load_wos_plaintext(path: str) -> pd.DataFrame:
    """WoS .txt and .ciw share the same plaintext format."""
    return pd.DataFrame(_parsers.parse_wos_data(path))


def _load_pubmed_txt(path: str) -> pd.DataFrame:
    return pd.DataFrame(_parsers.parse_pubmed_data(path))


def _load_cochrane_txt(path: str) -> pd.DataFrame:
    return pd.DataFrame(_parsers.parse_cochrane_data(path))


def _load_bib(path: str) -> pd.DataFrame:
    """Use bibtexparser to load .bib files into a record list."""
    from bibtexparser.bparser import BibTexParser

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    with open(path, "r", encoding="utf-8") as fh:
        bib_db = parser.parse_file(fh)
    return pd.DataFrame(bib_db.entries)


def _load_json(path: str) -> pd.DataFrame:
    """Load a JSON file containing either a list of records or a dict with
    an ``"entries"`` / ``"results"`` key.  Mostly useful for cached API
    responses."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        for k in ("results", "entries", "data"):
            if k in data and isinstance(data[k], list):
                data = data[k]
                break
    if not isinstance(data, list):
        raise ValueError(f"JSON at {path} is not a list of records.")
    return pd.DataFrame(data)


# --------------------------------------------------------------------------- #
#  DISPATCHER                                                                 #
# --------------------------------------------------------------------------- #

_LOADERS = {
    # Web of Science
    ("wos", "txt"):        _load_wos_plaintext,
    ("wos", "ciw"):        _load_wos_plaintext,
    ("wos", "bib"):        _load_bib,
    # Scopus
    ("scopus", "csv"):     _load_csv,
    ("scopus", "bib"):     _load_bib,
    # Dimensions
    ("dimensions", "csv"): _load_dimensions_csv,
    ("dimensions", "xlsx"):_load_dimensions_xlsx,
    # Lens
    ("lens", "csv"):       _load_csv,
    # PubMed
    ("pubmed", "txt"):     _load_pubmed_txt,
    ("pubmed", "json"):    _load_json,
    # Cochrane
    ("cochrane", "txt"):   _load_cochrane_txt,
    # OpenAlex (always JSON from the API or cached)
    ("openalex", "json"):  _load_json,
}
