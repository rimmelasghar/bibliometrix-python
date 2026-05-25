"""Dashboard compatibility matrix.

For every standardised CSV produced by the ETL (``out/etl/*.csv``), this
script reloads the file using exactly the same logic as the
``csv_unified_run`` handler in ``app.py`` (read as str, rehydrate list
columns, cast int columns) and then drives a handful of representative
analytical functions over the resulting DataFrame.

It prints a pass/fail matrix so we can demonstrate that the same
analysis code works across WoS, Scopus, PubMed, Dimensions, Lens and
Cochrane data via the standardised CSV.

Run from ``bibliometrix-python/``:

    ..\\env\\Scripts\\python.exe tests\\dashboard_compat.py
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import os
import sys
import traceback
from pathlib import Path

import pandas as pd

# Make the project importable when running ``python tests/dashboard_compat.py``
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from www.services.etl import SCHEMA  # noqa: E402
from www.services.etl.mappings import INT_COLUMNS, LIST_COLUMNS  # noqa: E402
from functions import (  # noqa: E402
    get_annual_production,
    get_average_citations,
    get_bradford_law,
    get_countries_production,
    get_lotka_law,
    get_main_informations,
    get_relevant_authors,
    get_relevant_sources,
)


class FakeReactive:
    """Minimal stand-in for ``shiny.reactive.Value``.

    The analytical functions read with ``.get()`` and a few of them
    (e.g. ``metaTagExtraction``) also write back with ``.set(M)`` —
    we mirror both so the same code paths work without a Shiny session.
    """

    def __init__(self, value):
        self._v = value

    def get(self):
        return self._v

    def set(self, value):
        self._v = value
        return self._v


def _parse_list(v):
    if isinstance(v, list):
        return v
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    s = str(v).strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
    for sep in [";", "|", ","]:
        if sep in s:
            return [t.strip() for t in s.split(sep) if t.strip()]
    return [s]


def load_unified_csv(path: Path) -> pd.DataFrame:
    """Mirror the ``csv_unified_run`` handler from ``app.py`` exactly."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in df.columns:
        if col in LIST_COLUMNS:
            df[col] = df[col].map(_parse_list)
        elif col in INT_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


# (label, callable(reactive_df) -> result)
ANALYSES = [
    ("main_info",         lambda r: get_main_informations(r)),
    ("annual_prod",       lambda r: get_annual_production(r)),
    ("avg_citations",     lambda r: get_average_citations(r)),
    ("relevant_sources",  lambda r: get_relevant_sources(r, 10)),
    ("relevant_authors",  lambda r: get_relevant_authors(r, 10)),
    ("bradford",          lambda r: get_bradford_law(r)),
    ("lotka",             lambda r: get_lotka_law(r)),
    ("countries_prod",    lambda r: get_countries_production(r)),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=2000,
        help="Cap each CSV to this many rows (0 = no cap). Default 2000 "
             "so PubMed (10k) does not stall the matrix.",
    )
    parser.add_argument(
        "--log",
        default="out/dashboard_compat_errors.log",
        help="Where to write full tracebacks for failed analyses.",
    )
    args = parser.parse_args()

    csv_dir = ROOT / "out" / "etl"
    if not csv_dir.is_dir():
        print(f"❌ Missing {csv_dir}. Run tests/run_etl.py --sweep first.")
        return 1

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        print(f"❌ No CSVs under {csv_dir}. Run tests/run_etl.py --sweep first.")
        return 1

    mandatory = [c for c, s in SCHEMA.items() if s.get("mandatory")]

    cap = args.max_rows if args.max_rows > 0 else None
    cap_msg = f" (capped to first {cap} rows each)" if cap else ""
    print(f"Found {len(csv_files)} CSV(s) under {csv_dir.relative_to(ROOT)}{cap_msg}\n")

    # header
    col_w = 22
    head = "CSV".ljust(40) + "rows".rjust(8) + "  " + "  ".join(
        name[:col_w].ljust(col_w) for name, _ in ANALYSES
    )
    print(head)
    print("-" * len(head))

    overall_pass = 0
    overall_fail = 0
    detailed_errors: list[tuple[str, str, str]] = []

    for csv in csv_files:
        try:
            df = load_unified_csv(csv)
            if cap is not None and len(df) > cap:
                df = df.head(cap).copy()
        except Exception as exc:
            print(f"{csv.name.ljust(40)} {'?':>8}  LOAD FAILED: {exc!r}")
            overall_fail += len(ANALYSES)
            continue

        missing = [c for c in mandatory if c not in df.columns]
        if missing:
            print(
                f"{csv.name.ljust(40)} {len(df):>8}  "
                f"SCHEMA FAIL — missing {missing}"
            )
            overall_fail += len(ANALYSES)
            continue

        reactive_df = FakeReactive(df)
        cells: list[str] = []
        for name, fn in ANALYSES:
            try:
                # Silence chatty analysis functions so the matrix stays readable.
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    fn(reactive_df)
                cells.append("PASS".ljust(col_w))
                overall_pass += 1
            except Exception as exc:
                short = type(exc).__name__
                cells.append(f"FAIL:{short}"[:col_w].ljust(col_w))
                detailed_errors.append(
                    (csv.name, name, f"{short}: {exc}\n{traceback.format_exc()}")
                )
                overall_fail += 1

        print(
            f"{csv.name.ljust(40)} {len(df):>8}  " + "  ".join(cells)
        )

    total = overall_pass + overall_fail
    print()
    print(f"Result: {overall_pass}/{total} analyses passed "
          f"({overall_fail} failed) across {len(csv_files)} CSV(s).")

    if detailed_errors:
        log_path = ROOT / args.log
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as fp:
            for csv_name, analysis, msg in detailed_errors:
                fp.write(f"\n=== [{csv_name}] {analysis} ===\n{msg}\n")
        print(f"Full tracebacks written to {log_path.relative_to(ROOT)}")

    return 0 if overall_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
