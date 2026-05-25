"""Smoke test: run convert2df() on every available local raw export and
print a 1-line per-source report.  Run from the project root::

    python tests/smoke_etl.py
"""
import os
import sys
import traceback

# Make sure we can import the package when run from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Import the etl subpackage directly to avoid triggering the dashboard's
# heavy www/services/__init__.py (which pulls in sklearn, matplotlib, ...).
sys.path.insert(0, os.path.join(ROOT, "www", "services"))

from etl import convert2df, validate  # noqa: E402


CASES = [
    ("wos",        "sources/Web_of_Science/WoS.txt", "txt"),
    ("wos",        "sources/Web_of_Science/WoS.ciw", "ciw"),
    ("wos",        "sources/Web_of_Science/WoS.bib", "bib"),
    ("scopus",     "sources/Scopus/Scopus.csv",     "csv"),
    ("scopus",     "sources/Scopus/Scopus.bib",     "bib"),
    ("dimensions", "sources/Dimensions/Dimensions.csv",  "csv"),
    ("dimensions", "sources/Dimensions/Dimensions.xlsx", "xlsx"),
    ("lens",       "sources/Lens/Lens.csv",         "csv"),
    ("pubmed",     "sources/PubMed/pubmed-allergicrh-set.txt", "txt"),
]


def run_one(source: str, path: str, ftype: str) -> None:
    label = f"[{source:10s} .{ftype:4s}]"
    if not os.path.exists(os.path.join(ROOT, path)):
        print(f"{label} SKIP  (file not found: {path})")
        return
    try:
        df = convert2df(source, os.path.join(ROOT, path), file_type=ftype)
    except Exception as exc:
        print(f"{label} FAIL  {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return
    report = validate(df, strict=False)
    status = "OK  " if report["ok"] else "WARN"
    issues = []
    if report["missing_mandatory"]:
        issues.append(f"miss={report['missing_mandatory']}")
    if report["null_columns"]:
        issues.append(f"null={report['null_columns']}")
    if report["wrong_type"]:
        issues.append(f"type={list(report['wrong_type'])}")
    extra = f"  ({'; '.join(issues)})" if issues else ""
    print(f"{label} {status}  rows={len(df):4d}  cols={len(df.columns)}  "
          f"AU_avg={df['AU'].map(len).mean():.1f}  TC_max={int(df['TC'].max() if len(df) else 0)}"
          f"{extra}")


def main() -> int:
    print(f"Running ETL smoke tests from {ROOT}\n")
    for case in CASES:
        run_one(*case)
    return 0


if __name__ == "__main__":
    sys.exit(main())
