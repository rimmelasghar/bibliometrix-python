from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List


# --------------------------------------------------------------------------- #
#  HELPERS                                                                    #
# --------------------------------------------------------------------------- #

def _is_null(v: Any) -> bool:
    """Robust null-check: ``None``, ``NaN``, empty string, the literal
    strings ``"nan"`` / ``"null"`` / ``"none"`` (case-insensitive)."""
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        return s in ("", "nan", "null", "none")
    return False


def _as_str(v: Any) -> str:
    """Coerce to a clean string, treating null sentinels as empty."""
    if _is_null(v):
        return ""
    return str(v).strip()


def _as_list(v: Any) -> List[Any]:
    """Coerce any value to a list (passes-through if already list/tuple)."""
    if _is_null(v):
        return []
    if isinstance(v, (list, tuple)):
        return [x for x in v if not _is_null(x)]
    return [v]


# --------------------------------------------------------------------------- #
#  SCALAR CASTS                                                               #
# --------------------------------------------------------------------------- #

def int_or_zero(v: Any) -> int:
    """Best-effort int cast; falls back to 0."""
    if _is_null(v):
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        m = re.search(r"-?\d+", str(v))
        return int(m.group()) if m else 0


_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2}|21\d{2})\b")


def year4(v: Any) -> int:
    """Extract a 4-digit year. Accepts ``"2024"``, ``"2024 Feb 2"``,
    ``2024.0``, etc.  Returns ``0`` if no year can be found."""
    if _is_null(v):
        return 0
    s = str(v)
    m = _YEAR_RE.search(s)
    return int(m.group(1)) if m else 0


def upper(v: Any) -> str:
    s = _as_str(v)
    return s.upper() if s else ""


def lower(v: Any) -> str:
    s = _as_str(v)
    return s.lower() if s else ""


def strip_newlines(v: Any) -> str:
    return re.sub(r"\s+", " ", _as_str(v)).strip()


def upper_strip_nl(v: Any) -> str:
    return strip_newlines(v).upper()


def first(v: Any) -> str:
    """First element if list-like, else value-as-string."""
    if isinstance(v, (list, tuple)):
        return _as_str(v[0]) if v else ""
    return _as_str(v)


def first_upper(v: Any) -> str:
    return first(v).upper()


def first_or_join(v: Any) -> str:
    """For WoS multi-line fields stored as ``[chunk1, chunk2, ...]``: join
    everything into a single whitespace-normalised string."""
    if isinstance(v, (list, tuple)):
        return strip_newlines(" ".join(_as_str(x) for x in v))
    return strip_newlines(_as_str(v))


def join_lines(v: Any) -> str:
    """Join multiple lines of a single logical field (typical for WoS TI)."""
    if isinstance(v, (list, tuple)):
        return strip_newlines(" ".join(_as_str(x) for x in v))
    return strip_newlines(_as_str(v))


def flatten_join(v: Any) -> Any:
    """When the raw value already came out of the parser as a list
    containing semicolon-joined strings, flatten and re-split."""
    if isinstance(v, (list, tuple)):
        return "; ".join(_as_str(x) for x in v if not _is_null(x))
    return _as_str(v)


# --------------------------------------------------------------------------- #
#  PAGE / DOI PARSERS                                                         #
# --------------------------------------------------------------------------- #

def page_start(v: Any) -> str:
    s = _as_str(v)
    if not s:
        return ""
    parts = re.split(r"[-–—]", s, maxsplit=1)
    return parts[0].strip()


def page_end(v: Any) -> str:
    s = _as_str(v)
    if not s:
        return ""
    parts = re.split(r"[-–—]", s, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def pubmed_doi(v: Any) -> str:
    """PubMed LID field looks like ``"10.1234/foo [doi]"`` or
    ``"S0001-1234(00)01234-5 [pii] 10.1234/foo [doi]"``."""
    s = _as_str(v)
    if not s:
        return ""
    m = re.search(r"(10\.\S+?)\s*\[doi\]", s, flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b10\.\S+", s)
    return m.group(0) if m else ""


def strip_doi_url(v: Any) -> str:
    s = _as_str(v)
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)


def prefix_pubmed(v: Any) -> str:
    s = _as_str(v)
    return f"PMID:{s}" if s else ""


# --------------------------------------------------------------------------- #
#  AUTHOR-NAME NORMALISERS                                                    #
# --------------------------------------------------------------------------- #

def strip_scopus_oid(v: Any) -> str:
    """Strip the ``" (OID-123456789)"`` suffix Scopus appends to author
    full-names."""
    return re.sub(r"\s*\(\d+\)\s*$", "", _as_str(v)).strip()


def comma_swap_name(v: Any) -> str:
    """Convert ``"Surname, First Names"`` → ``"Surname First Names"``
    (used to derive AF from PubMed's FAU)."""
    s = _as_str(v)
    if "," in s:
        sur, _, rest = s.partition(",")
        return f"{sur.strip()} {rest.strip()}".strip()
    return s


def name_to_surname_initials(v: Any) -> str:
    """``"Surname, First Middle"`` → ``"Surname FM"`` (WoS AU style)."""
    s = _as_str(v)
    if not s:
        return ""
    if "," in s:
        sur, _, rest = s.partition(",")
        initials = "".join(p[0].upper() for p in re.split(r"[\s\-]+", rest.strip()) if p)
        return f"{sur.strip()} {initials}".strip()
    # No comma — assume "First Middle Last" or already "Last F".
    parts = s.split()
    if len(parts) == 1:
        return parts[0]
    # "Last F." style already
    if len(parts[-1]) <= 3 and parts[-1].replace(".", "").isupper():
        return s
    initials = "".join(p[0].upper() for p in parts[:-1])
    return f"{parts[-1]} {initials}"


def name_to_surname_fullname(v: Any) -> str:
    """``"Surname, First Middle"`` → ``"Surname First Middle"``."""
    return comma_swap_name(v)


def lens_name_to_surname_initials(v: Any) -> str:
    """Lens stores ``"First Middle Last"``."""
    s = _as_str(v)
    if not s:
        return ""
    parts = s.split()
    if len(parts) == 1:
        return parts[0]
    initials = "".join(p[0].upper() for p in parts[:-1])
    return f"{parts[-1]} {initials}"


def lens_name_to_surname_fullname(v: Any) -> str:
    s = _as_str(v)
    if not s:
        return ""
    parts = s.split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[-1]} {' '.join(parts[:-1])}"


# --------------------------------------------------------------------------- #
#  MISC                                                                       #
# --------------------------------------------------------------------------- #

def strip_mesh_star(v: Any) -> str:
    """PubMed MeSH terms have ``"*"`` decoration marking the *major* topic
    qualifier — strip it for a clean keyword."""
    return _as_str(v).replace("*", "").strip()


def wos_clean_c1(v: Any) -> str:
    """WoS C1 lines look like ``"[Doe, J] Univ Naples..."``. Strip the
    leading bracketed author group so each entry is just the affiliation."""
    s = _as_str(v)
    return re.sub(r"^\s*\[.*?\]\s*", "", s).strip()


_SCOPUS_BIB_CITED_BY_RE = re.compile(r"[Cc]ited\s*[Bb]y\s*:\s*(\d+)")


def scopus_bib_cited_by(v: Any) -> int:
    """Extract ``"Cited By: NN"`` from Scopus bibtex 'note' field."""
    s = _as_str(v)
    if not s:
        return 0
    m = _SCOPUS_BIB_CITED_BY_RE.search(s)
    return int(m.group(1)) if m else 0


# --------------------------------------------------------------------------- #
#  BUILDERS  (operate on the FULL raw record)                                 #
# --------------------------------------------------------------------------- #

def builder_pubmed_affiliations(record: Dict[str, Any]) -> List[str]:
    """PubMed's MEDLINE format repeats ``AD - <affiliation>`` lines once per
    author block.  The rudimentary parser collapses them with ``";"`` so we
    just split-and-clean here."""
    raw = record.get("AD", "")
    if _is_null(raw):
        return []
    parts = [strip_newlines(p) for p in str(raw).split(";")]
    return [p for p in parts if p]


# ----- OpenAlex builders --------------------------------------------------- #

def builder_openalex_abstract(record: Dict[str, Any]) -> str:
    """OpenAlex returns an *inverted index*; reconstruct plain text."""
    idx = record.get("abstract_inverted_index")
    if not idx or not isinstance(idx, dict):
        return ""
    positions: Dict[int, str] = {}
    for word, locs in idx.items():
        for loc in locs:
            positions[loc] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))


def _openalex_authorships(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    auths = record.get("authorships") or []
    return auths if isinstance(auths, list) else []


def builder_openalex_authors_initials(record: Dict[str, Any]) -> List[str]:
    return [
        name_to_surname_initials(a.get("author", {}).get("display_name", ""))
        for a in _openalex_authorships(record)
        if a.get("author")
    ]


def builder_openalex_authors_fullname(record: Dict[str, Any]) -> List[str]:
    return [
        name_to_surname_fullname(a.get("author", {}).get("display_name", ""))
        for a in _openalex_authorships(record)
        if a.get("author")
    ]


def builder_openalex_affiliations(record: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for a in _openalex_authorships(record):
        for inst in a.get("institutions") or []:
            name = inst.get("display_name")
            if name:
                out.append(strip_newlines(name))
    return out


def builder_openalex_keywords(record: Dict[str, Any]) -> List[str]:
    kw = record.get("keywords") or []
    return [strip_newlines(k.get("display_name", "")) for k in kw if k.get("display_name")]


def builder_openalex_concepts(record: Dict[str, Any]) -> List[str]:
    concepts = record.get("concepts") or []
    return [strip_newlines(c.get("display_name", "")) for c in concepts if c.get("display_name")]


def builder_openalex_concept_names(record: Dict[str, Any]) -> List[str]:
    return builder_openalex_concepts(record)


def builder_openalex_references(record: Dict[str, Any]) -> List[str]:
    refs = record.get("referenced_works") or []
    return [str(r) for r in refs if r]


def _openalex_primary_location(record: Dict[str, Any]) -> Dict[str, Any]:
    loc = record.get("primary_location") or {}
    return loc if isinstance(loc, dict) else {}


def builder_openalex_source_name(record: Dict[str, Any]) -> str:
    src = _openalex_primary_location(record).get("source") or {}
    return strip_newlines(src.get("display_name", "")) if isinstance(src, dict) else ""


def builder_openalex_source_name_upper(record: Dict[str, Any]) -> str:
    return builder_openalex_source_name(record).upper()


def builder_openalex_pmid(record: Dict[str, Any]) -> str:
    ids = record.get("ids") or {}
    pmid = ids.get("pmid", "") if isinstance(ids, dict) else ""
    return re.sub(r"^https?://\S+/", "", _as_str(pmid))


def _openalex_biblio(record: Dict[str, Any]) -> Dict[str, Any]:
    b = record.get("biblio") or {}
    return b if isinstance(b, dict) else {}


def builder_openalex_volume(record: Dict[str, Any]) -> str:
    return _as_str(_openalex_biblio(record).get("volume"))


def builder_openalex_issue(record: Dict[str, Any]) -> str:
    return _as_str(_openalex_biblio(record).get("issue"))


def builder_openalex_first_page(record: Dict[str, Any]) -> str:
    return _as_str(_openalex_biblio(record).get("first_page"))


def builder_openalex_last_page(record: Dict[str, Any]) -> str:
    return _as_str(_openalex_biblio(record).get("last_page"))


def builder_openalex_oa_status(record: Dict[str, Any]) -> str:
    oa = record.get("open_access") or {}
    if not isinstance(oa, dict):
        return ""
    return _as_str(oa.get("oa_status"))


# --------------------------------------------------------------------------- #
#  DISPATCH TABLES                                                            #
# --------------------------------------------------------------------------- #

CASTS: Dict[str, Callable[[Any], Any]] = {
    # numeric / year
    "int_or_zero":               int_or_zero,
    "year4":                     year4,
    # text shaping
    "upper":                     upper,
    "lower":                     lower,
    "strip_newlines":            strip_newlines,
    "upper_strip_nl":            upper_strip_nl,
    "first":                     first,
    "first_upper":               first_upper,
    "first_or_join":             first_or_join,
    "join_lines":                join_lines,
    "flatten_join":              flatten_join,
    # pages / doi
    "page_start":                page_start,
    "page_end":                  page_end,
    "pubmed_doi":                pubmed_doi,
    "strip_doi_url":             strip_doi_url,
    "prefix_pubmed":             prefix_pubmed,
    # authors
    "strip_scopus_oid":          strip_scopus_oid,
    "comma_swap_name":           comma_swap_name,
    "name_to_surname_initials":  name_to_surname_initials,
    "name_to_surname_fullname":  name_to_surname_fullname,
    "lens_name_to_surname_initials": lens_name_to_surname_initials,
    "lens_name_to_surname_fullname": lens_name_to_surname_fullname,
    # misc
    "strip_mesh_star":           strip_mesh_star,
    "wos_clean_c1":              wos_clean_c1,
    "scopus_bib_cited_by":       scopus_bib_cited_by,
}

BUILDERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "pubmed_affiliations":              builder_pubmed_affiliations,
    "openalex_abstract":                builder_openalex_abstract,
    "openalex_authors_initials":        builder_openalex_authors_initials,
    "openalex_authors_fullname":        builder_openalex_authors_fullname,
    "openalex_affiliations":            builder_openalex_affiliations,
    "openalex_keywords":                builder_openalex_keywords,
    "openalex_concepts":                builder_openalex_concepts,
    "openalex_concept_names":           builder_openalex_concept_names,
    "openalex_references":              builder_openalex_references,
    "openalex_source_name":             builder_openalex_source_name,
    "openalex_source_name_upper":       builder_openalex_source_name_upper,
    "openalex_pmid":                    builder_openalex_pmid,
    "openalex_volume":                  builder_openalex_volume,
    "openalex_issue":                   builder_openalex_issue,
    "openalex_first_page":              builder_openalex_first_page,
    "openalex_last_page":               builder_openalex_last_page,
    "openalex_oa_status":               builder_openalex_oa_status,
}
