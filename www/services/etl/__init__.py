"""
bibliometrix-python ETL package.

A robust, source-agnostic Extract-Transform-Load pipeline that converts
heterogeneous bibliographic exports (Web of Science, Scopus, Dimensions,
PubMed, Lens, Cochrane) and live API responses (OpenAlex, PubMed E-utilities)
into the unified WoS-style DataFrame expected by every analytical function
in ``functions/`` and ``www/services/``.

Design highlights
-----------------
* **Single entry point**: :func:`convert2df` (mirrors R's ``bibliometrix::convert2df``).
* **Mapping dictionaries** (no hardcoded ``if source == ...`` branches inside
  transformations) — see :mod:`.mappings`.
* **Strict type contracts** — list-fields, scalar-string fields and numeric
  fields are enforced (see :mod:`.transformers` and :mod:`.validator`).
* **No NaN/None** ever survives in the output (lists become ``[]``,
  scalars become ``""``, ``TC`` becomes ``0``).
* **Delegated SR generation** — reuses the existing
  ``format_sr_column`` helper from ``www.services.format_functions``.

Typical usage::

    from www.services.etl import convert2df

    df = convert2df(source="scopus", file_path="sources/Scopus/Scopus.csv")
    df = convert2df(source="openalex", query="machine learning", max_results=200)
"""

from .standardizer import convert2df
from .validator import validate, ValidationError
from .mappings import SCHEMA, MANDATORY_COLUMNS, LIST_COLUMNS, SCALAR_STR_COLUMNS
from .api_retriever import fetch_openalex, fetch_pubmed, fetch_dataframe

__all__ = [
    "convert2df",
    "validate",
    "ValidationError",
    "SCHEMA",
    "MANDATORY_COLUMNS",
    "LIST_COLUMNS",
    "SCALAR_STR_COLUMNS",
    "fetch_openalex",
    "fetch_pubmed",
    "fetch_dataframe",
]
