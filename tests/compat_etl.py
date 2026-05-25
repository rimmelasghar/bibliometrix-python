"""
Compatibility test: run every easily-callable analytical ``get_*`` function
on the DataFrames produced by ``convert2df`` for every supported source,
and report pass / fail.

The legacy functions expect a "reactive-like" object exposing ``.get()``.
We wrap our DataFrames in a tiny ``ReactiveLike`` shim to mimic that.
"""

from __future__ import annotations

import io
import os
import sys
import traceback
import warnings
from contextlib import redirect_stdout, redirect_stderr

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# Also let the legacy code import its own modules.
sys.path.insert(0, os.path.join(ROOT, "www", "services"))

warnings.filterwarnings("ignore")

from etl import convert2df  # noqa: E402  (after sys.path tweak)


# --------------------------------------------------------------------------- #
class ReactiveLike:
    """Tiny shim mimicking shiny's reactive Value: exposes ``.get()`` / ``.set()``."""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def get(self) -> pd.DataFrame:
        return self._df

    def set(self, value) -> None:
        self._df = value

    # Some legacy functions call the reactive like a function: ``df()``.
    def __call__(self):
        return self._df


# --------------------------------------------------------------------------- #
SOURCES_DIR = os.path.join(ROOT, "sources")

DATASETS = [
    ("wos",        os.path.join("Web_of_Science", "WoS.txt"),         "txt"),
    ("scopus",     os.path.join("Scopus",         "Scopus.csv"),      "csv"),
    ("dimensions", os.path.join("Dimensions",     "Dimensions.csv"),  "csv"),
    ("lens",       os.path.join("Lens",           "Lens.csv"),        "csv"),
    ("pubmed",     os.path.join("PubMed",         "pubmed-allergicrh-set.txt"), "txt"),
]


def load_dataframes() -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for source, fname, ft in DATASETS:
        path = os.path.join(SOURCES_DIR, fname)
        if not os.path.exists(path):
            print(f"  [skip] {source}: {fname} not found")
            continue
        try:
            df = convert2df(source, path, file_type=ft)
            out[source] = df
            print(f"  [ok]   {source:11s} -> {df.shape[0]} rows x {df.shape[1]} cols")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {source}: {exc!r}")
    return out


# --------------------------------------------------------------------------- #
# Each entry: (label, callable that takes a ReactiveLike df)
def build_tests():
    import functions as F

    return [
        ("get_main_informations",            lambda d: F.get_main_informations(d)),
        ("get_annual_production",            lambda d: F.get_annual_production(d)),
        ("get_average_citations",            lambda d: F.get_average_citations(d)),
        ("get_bradford_law",                 lambda d: F.get_bradford_law(d)),
        ("get_countries_production",         lambda d: F.get_countries_production(d)),
        ("get_filters",                      lambda d: F.get_filters(d)),
        ("get_lotka_law",                    lambda d: F.get_lotka_law(d)),
        ("get_relevant_sources",             lambda d: F.get_relevant_sources(d, 20)),
        ("get_relevant_authors",             lambda d: F.get_relevant_authors(d, 20)),
        ("get_relevant_affiliations",        lambda d: F.get_relevant_affiliations(d, 20, False)),
        ("get_local_cited_sources",          lambda d: F.get_local_cited_sources(d, 20)),
        ("get_local_cited_authors",          lambda d: F.get_local_cited_authors(d, 20)),
        ("get_local_cited_documents",        lambda d: F.get_local_cited_documents(d, 20, ";")),
        ("get_local_cited_refs",             lambda d: F.get_local_cited_refs(d, 20, ";")),
        ("get_corresponding_author_countries", lambda d: F.get_corresponding_author_countries(d, 20)),
        ("get_countries_production_over_time", lambda d: F.get_countries_production_over_time(d, 20)),
        ("get_author_production_over_time",    lambda d: F.get_author_production_over_time(d, 20)),
        ("get_affiliation_production_over_time", lambda d: F.get_affiliation_production_over_time(d, 20)),
        ("get_sources_production",           lambda d: F.get_sources_production(d, 20, 1)),
        ("get_authors_local_impact",         lambda d: F.get_authors_local_impact(d, 20, "h_index")),
        ("get_sources_local_impact",         lambda d: F.get_sources_local_impact(d, 20, "h_index")),
        ("get_cited_documents",              lambda d: F.get_cited_documents(d, 20, "Global Citations")),
        ("get_cited_countries",              lambda d: F.get_cited_countries(d, 20, "Global Citations")),
        ("get_world_map_collaboration",      lambda d: F.get_world_map_collaboration(d)),
    ]


# --------------------------------------------------------------------------- #
def run_one(label, fn, reactive):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            fn(reactive)
        return None
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc(limit=2)
        first = tb.strip().splitlines()[-1]
        return f"{type(exc).__name__}: {first[:200]}"


def main():
    print("=" * 72)
    print("Building DataFrames via convert2df ...")
    print("=" * 72)
    dfs = load_dataframes()

    tests = build_tests()
    print("\n" + "=" * 72)
    print("Running analytical functions against each dataset")
    print("=" * 72)

    table = {src: {} for src in dfs}
    for src, df in dfs.items():
        reactive = ReactiveLike(df)
        print(f"\n--- {src} ({df.shape[0]} rows) ---")
        for label, fn in tests:
            err = run_one(label, fn, reactive)
            mark = "PASS" if err is None else "FAIL"
            table[src][label] = (mark, err)
            print(f"  {mark}  {label}" + (f"   |  {err}" if err else ""))

    # Summary matrix
    print("\n" + "=" * 72)
    print("Summary (PASS/FAIL matrix)")
    print("=" * 72)
    sources = list(dfs)
    width = max(len(l) for l, _ in tests)
    header = "  " + " " * width + "  " + "  ".join(f"{s[:7]:>7s}" for s in sources)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for label, _ in tests:
        row = f"  {label:<{width}s}  "
        for s in sources:
            row += f"{table[s][label][0]:>7s}  "
        print(row)

    n_total = sum(len(table[s]) for s in sources)
    n_pass  = sum(1 for s in sources for v in table[s].values() if v[0] == "PASS")
    print(f"\nTotal: {n_pass}/{n_total} PASS")


if __name__ == "__main__":
    main()
