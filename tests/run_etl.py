"""
Manual ETL runner / CSV exporter.

Run the unified ETL on a single file (or a live API query) and dump the
resulting WoS-style DataFrame to a CSV so you can inspect it.

Usage
-----
    # File-based (auto-detects file_type from extension)
    python tests/run_etl.py --source scopus --file sources/Scopus/Scopus.bib
    python tests/run_etl.py --source wos    --file sources/new/WOS/WoS_collection.txt
    python tests/run_etl.py --source pubmed --file sources/PubMed/pubmed-allergicrh-set.txt
    python tests/run_etl.py --source dimensions --file sources/Dimensions/Dimensions.csv
    python tests/run_etl.py --source lens   --file sources/Lens/Lens.csv
    python tests/run_etl.py --source cochrane --file sources/Cochrane/citation-export.txt

    # Live API
    python tests/run_etl.py --source openalex --query "bibliometrics" --max 50
    python tests/run_etl.py --source pubmed   --query "allergic rhinitis" --max 30

    # Sweep every sample under sources/ in one go
    python tests/run_etl.py --sweep

Each successful run prints a short summary and writes the resulting CSV
into ``out/etl/`` next to the project root.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

# Make sure the package is importable when this script is executed
# directly (``python tests/run_etl.py``).
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from www.services.etl import convert2df, validate  # noqa: E402
from www.services.etl import fetch_dataframe       # noqa: E402


OUT_DIR = ROOT / "out" / "etl"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# A representative sample per source for ``--sweep``.
SAMPLES = [
    ("scopus",     "sources/Scopus/Scopus.bib"),
    ("wos",        "sources/new/WOS/WoS_collection.txt"),
    ("wos",        "sources/Web_of_Science/WoS.bib"),
    ("pubmed",     "sources/PubMed/pubmed-allergicrh-set.txt"),
    ("dimensions", "sources/Dimensions/Dimensions.csv"),
    ("lens",       "sources/Lens/Lens.csv"),
    ("cochrane",   "sources/Cochrane/citation-export.txt"),
]


def _print_summary(df, source: str, origin: str) -> None:
    report = df.attrs.get("etl_report") or validate(df)
    ok = "OK " if report.get("ok") else "WARN"
    print(
        f"  [{ok}] {source:<10} rows={len(df):<5} cols={len(df.columns):<3} "
        f"missing_mandatory={report.get('missing_mandatory', [])}"
    )


def _safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)


def run_file(source: str, file_path: str, *, validate_strict: bool = False) -> Path:
    print(f"--> ETL  source={source!r}  file={file_path!r}")
    t0 = time.perf_counter()
    df = convert2df(source, file_path, validate_strict=validate_strict)
    dt = time.perf_counter() - t0

    stem = _safe_name(Path(file_path).stem)
    out = OUT_DIR / f"{source}__{stem}.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}  ({dt*1000:.0f} ms)")
    _print_summary(df, source, file_path)
    return out


def run_api(source: str, query: str, max_results: int, mailto: Optional[str]) -> Path:
    print(f"--> ETL  source={source!r}  query={query!r}  max={max_results}")
    t0 = time.perf_counter()
    kwargs = {"mailto": mailto} if (source == "openalex" and mailto) else {}
    df = fetch_dataframe(source, query, max_results=max_results, **kwargs)
    dt = time.perf_counter() - t0

    out = OUT_DIR / f"{source}__api__{_safe_name(query)[:40]}.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)}  ({dt*1000:.0f} ms)")
    _print_summary(df, source, f"api:{query}")
    return out


def sweep() -> int:
    ok = fail = 0
    for source, rel in SAMPLES:
        p = ROOT / rel
        if not p.exists():
            print(f"  [SKIP] {source:<10} missing {rel}")
            continue
        try:
            run_file(source, str(p))
            ok += 1
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  [FAIL] {source:<10} {rel}: {exc!r}")
            traceback.print_exc()
    print(f"\nSweep complete: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", help="wos | scopus | pubmed | dimensions | lens | cochrane | openalex")
    p.add_argument("--file", help="Path to an export file (relative paths resolved against the project root)")
    p.add_argument("--query", help="Live API query (OpenAlex or PubMed)")
    p.add_argument("--max", type=int, default=50, help="Max records for live API (default 50)")
    p.add_argument("--mailto", default=None, help="Polite-pool email for OpenAlex (optional)")
    p.add_argument("--strict", action="store_true", help="Raise on validation contract violations")
    p.add_argument("--sweep", action="store_true", help="Run all bundled samples")
    args = p.parse_args(argv)

    if args.sweep:
        return sweep()

    if not args.source:
        p.error("--source is required (or use --sweep)")

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            p.error(f"file not found: {path}")
        run_file(args.source, str(path), validate_strict=args.strict)
        return 0

    if args.query:
        run_api(args.source, args.query, args.max, args.mailto)
        return 0

    p.error("provide either --file <path> or --query <text> (or --sweep)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
