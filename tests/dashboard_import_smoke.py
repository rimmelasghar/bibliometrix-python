"""Smoke test: exercise the dashboard's data-upload code-path
(``biblio_json``) through the new ETL fast-path for every supported DB.
"""
from __future__ import annotations

import io
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from www.services.format_functions import biblio_json  # noqa: E402

CASES = [
    ("wos",        "sources/Web_of_Science/WoS.txt",           "WoS.txt"),
    ("scopus",     "sources/Scopus/Scopus.csv",                "Scopus.csv"),
    ("dimensions", "sources/Dimensions/Dimensions.csv",        "Dimensions.csv"),
    ("lens",       "sources/Lens/Lens.csv",                    "Lens.csv"),
    ("pubmed",     "sources/PubMed/pubmed-allergicrh-set.txt", "pubmed.txt"),
]

all_ok = True
for src, path, fname in CASES:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"SKIP   {src:11s}  (missing {path})")
        continue
    js = biblio_json(full, src, fname, "surname")
    df = pd.read_json(io.StringIO(js))
    db_label = df.iloc[0]["DB"]
    py = df.iloc[0]["PY"]
    sr_set = int(df["SR"].notna().sum())
    print(f"PASS   {src:11s}  rows={len(df):5d}  cols={len(df.columns):2d}  "
          f"DB={db_label!r}  PY={py}  SR_set={sr_set}")
    if sr_set == 0:
        all_ok = False

print("OK" if all_ok else "FAIL")
sys.exit(0 if all_ok else 1)
