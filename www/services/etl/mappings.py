from __future__ import annotations

from typing import Any, Dict, List, Set


# --------------------------------------------------------------------------- #
#  TARGET SCHEMA                                                              #
# --------------------------------------------------------------------------- #

# The full WoS-style target schema. Order is preserved for CSV exports.
# type ∈ {"str", "int", "list"}.
SCHEMA: Dict[str, Dict[str, Any]] = {
    "DB":   {"type": "str", "mandatory": True,  "desc": "Database source"},
    "UT":   {"type": "str", "mandatory": True,  "desc": "Unique article identifier"},
    "DI":   {"type": "str", "mandatory": True,  "desc": "DOI"},
    "PMID": {"type": "str", "mandatory": False, "desc": "PubMed ID"},
    "TI":   {"type": "str", "mandatory": True,  "desc": "Document title"},
    "SO":   {"type": "str", "mandatory": True,  "desc": "Publication name / source"},
    "JI":   {"type": "str", "mandatory": False, "desc": "ISO source abbreviation"},
    "PY":   {"type": "int", "mandatory": True,  "desc": "Publication year (4-digit)"},
    "DT":   {"type": "str", "mandatory": False, "desc": "Document type"},
    "LA":   {"type": "str", "mandatory": False, "desc": "Language"},
    "TC":   {"type": "int", "mandatory": True,  "desc": "Times cited"},
    "AU":   {"type": "list", "mandatory": True, "desc": "Authors (Surname Initials)"},
    "AF":   {"type": "list", "mandatory": False, "desc": "Author full names"},
    "C1":   {"type": "list", "mandatory": True, "desc": "Author affiliations"},
    "RP":   {"type": "str", "mandatory": False, "desc": "Reprint / corresponding address"},
    "CR":   {"type": "list", "mandatory": False, "desc": "Cited references"},
    "DE":   {"type": "list", "mandatory": False, "desc": "Author keywords"},
    "ID":   {"type": "list", "mandatory": False, "desc": "Index / Keywords-Plus"},
    "AB":   {"type": "str", "mandatory": False, "desc": "Abstract"},
    "VL":   {"type": "str", "mandatory": False, "desc": "Volume"},
    "IS":   {"type": "str", "mandatory": False, "desc": "Issue"},
    "BP":   {"type": "str", "mandatory": False, "desc": "Beginning page"},
    "EP":   {"type": "str", "mandatory": False, "desc": "Ending page"},
    "SR":   {"type": "str", "mandatory": True,  "desc": "Short reference (calculated)"},
    # --- Optional extended columns kept for backwards compatibility with
    #     the existing dashboard / analytical functions ---------------------
    "AU_UN":  {"type": "list", "mandatory": False, "desc": "Authors' universities"},
    "AU1_UN": {"type": "str",  "mandatory": False, "desc": "First author's university"},
    "SN":     {"type": "str",  "mandatory": False, "desc": "ISSN"},
    "PU":     {"type": "str",  "mandatory": False, "desc": "Publisher"},
    "OA":     {"type": "str",  "mandatory": False, "desc": "Open access flag"},
    "OI":     {"type": "list", "mandatory": False, "desc": "ORCID identifiers"},
    "EM":     {"type": "list", "mandatory": False, "desc": "Author e-mails"},
    "FU":     {"type": "str",  "mandatory": False, "desc": "Funding details"},
    "FX":     {"type": "str",  "mandatory": False, "desc": "Funding text"},
    "SC":     {"type": "list", "mandatory": False, "desc": "Fields of research"},
    "WC":     {"type": "list", "mandatory": False, "desc": "WoS categories"},
}

MANDATORY_COLUMNS: List[str] = [k for k, v in SCHEMA.items() if v["mandatory"]]
LIST_COLUMNS: Set[str] = {k for k, v in SCHEMA.items() if v["type"] == "list"}
SCALAR_STR_COLUMNS: Set[str] = {k for k, v in SCHEMA.items() if v["type"] == "str"}
INT_COLUMNS: Set[str] = {k for k, v in SCHEMA.items() if v["type"] == "int"}


# --------------------------------------------------------------------------- #
#  DATABASE-CODE LABELS  (the value stored in the DB column)                  #
# --------------------------------------------------------------------------- #

DB_LABELS: Dict[str, str] = {
    # NB: legacy ``www/services`` modules (e.g. ``histnetwork.py``,
    # ``biblionetwork.py``, ``metatagextraction.py``) compare the DB
    # column against these exact strings, so we keep the legacy
    # spelling to stay compatible with downstream analytical functions.
    "wos":        "Web_of_Science",
    "scopus":     "Scopus",
    "pubmed":     "PubMed",
    "dimensions": "Dimensions",
    "lens":       "Lens",
    "cochrane":   "Cochrane",
    "openalex":   "OpenAlex",
}


# --------------------------------------------------------------------------- #
#  PER-SOURCE FIELD MAPPINGS                                                  #
# --------------------------------------------------------------------------- #
#  Each top-level key is "<source>_<file_type>" (file_type without leading
#  dot).  The dispatcher in :mod:`.extractors` picks the right entry.
# --------------------------------------------------------------------------- #

MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {}


# ---------- SCOPUS (.csv) -------------------------------------------------- #
MAPPINGS["scopus_csv"] = {
    "TI":   {"src": "Title"},
    "AB":   {"src": "Abstract"},
    "AU":   {"src": "Authors",            "list": True, "sep": "; "},
    "AF":   {"src": "Author full names",  "list": True, "sep": "; ",
             "cast": "strip_scopus_oid"},
    "C1":   {"src": "Affiliations",       "list": True, "sep": "; "},
    "DE":   {"src": "Author Keywords",    "list": True, "sep": "; "},
    "ID":   {"src": "Index Keywords",     "list": True, "sep": "; "},
    "CR":   {"src": "References",         "list": True, "sep": "; "},
    "TC":   {"src": "Cited by",           "cast": "int_or_zero"},
    "PY":   {"src": "Year",               "cast": "year4"},
    "SO":   {"src": "Source title",       "cast": "upper"},
    "JI":   {"src": "Abbreviated Source Title"},
    "DI":   {"src": "DOI"},
    "PMID": {"src": "PubMed ID"},
    "UT":   {"src": "EID"},
    "VL":   {"src": "Volume"},
    "IS":   {"src": "Issue"},
    "BP":   {"src": "Page start"},
    "EP":   {"src": "Page end"},
    "DT":   {"src": "Document Type"},
    "LA":   {"src": "Language of Original Document"},
    "RP":   {"src": "Correspondence Address"},
    "SN":   {"src": "ISSN"},
    "PU":   {"src": "Publisher"},
    "OA":   {"src": "Open Access"},
    "FU":   {"src": "Funding Details"},
    "FX":   {"src": "Funding Texts"},
}

# ---------- SCOPUS (.bib) -------------------------------------------------- #
MAPPINGS["scopus_bib"] = {
    "TI":   {"src": "title"},
    "AB":   {"src": "abstract"},
    "AU":   {"src": "author",       "list": True, "sep": " and ",
             "cast": "name_to_surname_initials"},
    "AF":   {"src": "author",       "list": True, "sep": " and ",
             "cast": "name_to_surname_fullname"},
    "DE":   {"src": "author_keywords", "list": True, "sep": "; "},
    "ID":   {"src": "keywords",     "list": True, "sep": "; "},
    "DI":   {"src": "doi"},
    "PY":   {"src": "year",         "cast": "year4"},
    "SO":   {"src": "journal",      "cast": "upper"},
    "JI":   {"src": "journal"},
    "VL":   {"src": "volume"},
    "IS":   {"src": "number"},
    "BP":   {"src": "pages",        "cast": "page_start"},
    "EP":   {"src": "pages",        "cast": "page_end"},
    "DT":   {"src": "document_type"},
    "TC":   {"src": "note",         "cast": "scopus_bib_cited_by"},
    "UT":   {"src": "ID"},
    "PU":   {"src": "publisher"},
    "SN":   {"src": "issn"},
}

# ---------- WEB OF SCIENCE (.txt / .ciw) ----------------------------------- #
MAPPINGS["wos_txt"] = {
    "TI":   {"src": "TI",  "cast": "join_lines"},
    "AB":   {"src": "AB",  "cast": "first_or_join"},
    "AU":   {"src": "AU",  "list": True},
    "AF":   {"src": "AF",  "list": True},
    "C1":   {"src": "C1",  "list": True, "cast": "wos_clean_c1"},
    "CR":   {"src": "CR",  "list": True},
    "DE":   {"src": "DE",  "list": True, "sep": "; ", "cast": "flatten_join"},
    "ID":   {"src": "ID",  "list": True, "sep": "; ", "cast": "flatten_join"},
    "TC":   {"src": "TC",  "cast": "int_or_zero"},
    "PY":   {"src": "PY",  "cast": "year4"},
    "SO":   {"src": "SO",  "cast": "first_upper"},
    "JI":   {"src": "JI",  "cast": "first"},
    "DI":   {"src": "DI",  "cast": "first"},
    "PMID": {"src": "PM",  "cast": "first"},
    "UT":   {"src": "UT",  "cast": "first"},
    "VL":   {"src": "VL",  "cast": "first"},
    "IS":   {"src": "IS",  "cast": "first"},
    "BP":   {"src": "BP",  "cast": "first"},
    "EP":   {"src": "EP",  "cast": "first"},
    "DT":   {"src": "DT",  "cast": "first"},
    "LA":   {"src": "LA",  "cast": "first"},
    "RP":   {"src": "RP",  "cast": "first"},
    "SN":   {"src": "SN",  "cast": "first"},
    "PU":   {"src": "PU",  "cast": "first"},
    "OA":   {"src": "OA",  "cast": "first"},
    "OI":   {"src": "OI",  "list": True, "sep": "; ", "cast": "flatten_join"},
    "EM":   {"src": "EM",  "list": True, "sep": "; ", "cast": "flatten_join"},
    "FU":   {"src": "FU",  "cast": "first_or_join"},
    "FX":   {"src": "FX",  "cast": "first_or_join"},
    "SC":   {"src": "SC",  "list": True, "sep": "; ", "cast": "flatten_join"},
    "WC":   {"src": "WC",  "list": True, "sep": "; ", "cast": "flatten_join"},
}
MAPPINGS["wos_ciw"] = MAPPINGS["wos_txt"]

# ---------- WEB OF SCIENCE (.bib) ------------------------------------------ #
MAPPINGS["wos_bib"] = {
    "TI":   {"src": "title"},
    "AB":   {"src": "abstract", "cast": "strip_newlines"},
    "AU":   {"src": "author",   "list": True, "sep": " and ",
             "cast": "name_to_surname_initials"},
    "AF":   {"src": "author",   "list": True, "sep": " and ",
             "cast": "name_to_surname_fullname"},
    "DE":   {"src": "keywords", "list": True, "sep": "; ", "cast": "strip_newlines"},
    "CR":   {"src": "cited-references", "list": True, "sep": "\n"},
    "TC":   {"src": "times-cited", "cast": "int_or_zero"},
    "PY":   {"src": "year",     "cast": "year4"},
    "SO":   {"src": ["journal", "booktitle"], "cast": "upper_strip_nl"},
    "JI":   {"src": ["journal", "booktitle"], "cast": "strip_newlines"},
    "DI":   {"src": "doi"},
    "UT":   {"src": "unique-id"},
    "VL":   {"src": "volume"},
    "IS":   {"src": "number"},
    "BP":   {"src": "pages",    "cast": "page_start"},
    "EP":   {"src": "pages",    "cast": "page_end"},
    "DT":   {"src": "type"},
    "LA":   {"src": "language"},
    "PU":   {"src": "publisher"},
    "SN":   {"src": "issn"},
}

# ---------- PUBMED (.txt — MEDLINE export) --------------------------------- #
MAPPINGS["pubmed_txt"] = {
    "TI":   {"src": "TI"},
    "AB":   {"src": "AB"},
    "AU":   {"src": "AU",  "list": True, "sep": ";"},
    "AF":   {"src": "FAU", "list": True, "sep": ";",
             "cast": "comma_swap_name"},
    "C1":   {"builder": "pubmed_affiliations"},
    "DE":   {"src": "MH",  "list": True, "sep": ";", "cast": "strip_mesh_star"},
    "ID":   {"src": "OT",  "list": True, "sep": ";"},
    "CR":   {"default": []},
    "TC":   {"default": 0},
    "PY":   {"src": "DP",  "cast": "year4"},
    "SO":   {"src": ["JT", "TA"], "cast": "upper"},
    "JI":   {"src": "TA"},
    "DI":   {"src": "LID", "cast": "pubmed_doi"},
    "PMID": {"src": "PMID"},
    "UT":   {"src": "PMID", "cast": "prefix_pubmed"},
    "VL":   {"src": "VI"},
    "IS":   {"src": "IP"},
    "BP":   {"src": "PG",  "cast": "page_start"},
    "EP":   {"src": "PG",  "cast": "page_end"},
    "DT":   {"src": "PT"},
    "LA":   {"src": "LA"},
    "PU":   {"src": "PB"},
    "SN":   {"src": "IS"},
}
# API retriever returns dict records of identical shape — reuse the
# MEDLINE-style mapping so the same EXTRACT/TRANSFORM logic applies.
MAPPINGS["pubmed_json"] = MAPPINGS["pubmed_txt"]

# ---------- DIMENSIONS (.csv / .xlsx) -------------------------------------- #
MAPPINGS["dimensions_csv"] = {
    "TI":   {"src": "Title"},
    "AB":   {"src": "Abstract"},
    "AU":   {"src": "Authors", "list": True, "sep": "; ",
             "cast": "name_to_surname_initials"},
    "AF":   {"src": "Authors", "list": True, "sep": "; ",
             "cast": "name_to_surname_fullname"},
    "C1":   {"src": "Authors Affiliations", "list": True, "sep": "; "},
    "DE":   {"src": "MeSH terms",  "list": True, "sep": "; "},
    "ID":   {"src": "MeSH terms",  "list": True, "sep": "; "},
    "CR":   {"default": []},
    "TC":   {"src": "Times cited", "cast": "int_or_zero"},
    "PY":   {"src": "PubYear",     "cast": "year4"},
    "SO":   {"src": "Source title", "cast": "upper"},
    "JI":   {"src": "Source title"},
    "DI":   {"src": "DOI"},
    "PMID": {"src": "PMID"},
    "UT":   {"src": "Publication ID"},
    "VL":   {"src": "Volume"},
    "IS":   {"src": "Issue"},
    "BP":   {"src": "Pagination",  "cast": "page_start"},
    "EP":   {"src": "Pagination",  "cast": "page_end"},
    "DT":   {"src": "Publication Type"},
    "OA":   {"src": "Open Access"},
    "FU":   {"src": "Funding"},
    "SC":   {"src": "Fields of Research (ANZSRC 2020)", "list": True, "sep": "; "},
    "RP":   {"src": "Corresponding Authors"},
}
MAPPINGS["dimensions_xlsx"] = MAPPINGS["dimensions_csv"]

# ---------- LENS.ORG (.csv) ------------------------------------------------ #
MAPPINGS["lens_csv"] = {
    "TI":   {"src": "Title"},
    "AB":   {"src": "Abstract"},
    "AU":   {"src": "Author/s", "list": True, "sep": "; ",
             "cast": "lens_name_to_surname_initials"},
    "AF":   {"src": "Author/s", "list": True, "sep": "; ",
             "cast": "lens_name_to_surname_fullname"},
    "DE":   {"src": "Keywords",  "list": True, "sep": "; "},
    "ID":   {"src": "MeSH Terms", "list": True, "sep": "; "},
    "CR":   {"src": "References", "list": True, "sep": "; "},
    "TC":   {"src": "Citing Works Count", "cast": "int_or_zero"},
    "PY":   {"src": "Publication Year",   "cast": "year4"},
    "SO":   {"src": "Source Title", "cast": "upper"},
    "JI":   {"src": "Source Title"},
    "DI":   {"src": "DOI"},
    "PMID": {"src": "PMID"},
    "UT":   {"src": "Lens ID"},
    "VL":   {"src": "Volume"},
    "IS":   {"src": "Issue Number"},
    "BP":   {"src": "Start Page"},
    "EP":   {"src": "End Page"},
    "DT":   {"src": "Publication Type"},
    "OA":   {"src": "Is Open Access"},
    "PU":   {"src": "Publisher"},
    "SN":   {"src": "ISSNs"},
    "FU":   {"src": "Funding"},
    "SC":   {"src": "Fields of Study", "list": True, "sep": "; "},
}

# ---------- COCHRANE (.txt) ------------------------------------------------ #
MAPPINGS["cochrane_txt"] = {
    "TI":   {"src": "TI"},
    "AB":   {"src": "AB"},
    "AU":   {"src": "AU", "list": True, "sep": "; "},
    "DE":   {"src": "KY", "list": True, "sep": ";"},
    "ID":   {"default": []},
    "C1":   {"default": []},
    "CR":   {"default": []},
    "TC":   {"default": 0},
    "PY":   {"src": "YR", "cast": "year4"},
    "SO":   {"src": "SO", "cast": "upper"},
    "JI":   {"src": "SO"},
    "DI":   {"src": "DOI"},
    "VL":   {"src": "VL"},
    "IS":   {"src": "IS"},
    "DT":   {"default": "Article"},
}

# ---------- OPENALEX (JSON returned by API) -------------------------------- #
# The OpenAlex retriever flattens each "work" object into a dict whose keys
# are listed below.  Builder primitives are used for fields that require
# walking nested JSON structures.
MAPPINGS["openalex_json"] = {
    "TI":   {"src": "title"},
    "AB":   {"builder": "openalex_abstract"},
    "AU":   {"builder": "openalex_authors_initials"},
    "AF":   {"builder": "openalex_authors_fullname"},
    "C1":   {"builder": "openalex_affiliations"},
    "DE":   {"builder": "openalex_keywords"},
    "ID":   {"builder": "openalex_concepts"},
    "CR":   {"builder": "openalex_references"},
    "TC":   {"src": "cited_by_count", "cast": "int_or_zero"},
    "PY":   {"src": "publication_year", "cast": "year4"},
    "SO":   {"builder": "openalex_source_name_upper"},
    "JI":   {"builder": "openalex_source_name"},
    "DI":   {"src": "doi", "cast": "strip_doi_url"},
    "PMID": {"builder": "openalex_pmid"},
    "UT":   {"src": "id"},
    "VL":   {"builder": "openalex_volume"},
    "IS":   {"builder": "openalex_issue"},
    "BP":   {"builder": "openalex_first_page"},
    "EP":   {"builder": "openalex_last_page"},
    "DT":   {"src": "type"},
    "LA":   {"src": "language"},
    "OA":   {"builder": "openalex_oa_status"},
    "SC":   {"builder": "openalex_concept_names"},
}


def get_mapping(source: str, file_type: str) -> Dict[str, Dict[str, Any]]:
    """Return the mapping dictionary for the given source / file-type pair.

    Parameters
    ----------
    source : str
        Lower-case source identifier (``wos``, ``scopus``, ``pubmed``,
        ``dimensions``, ``lens``, ``cochrane``, ``openalex``).
    file_type : str
        File-extension *without* leading dot (``csv``, ``xlsx``, ``txt``,
        ``ciw``, ``bib``, ``json``).
    """
    key = f"{source.lower()}_{file_type.lstrip('.').lower()}"
    if key not in MAPPINGS:
        raise KeyError(
            f"No ETL mapping defined for source='{source}' file_type='{file_type}'. "
            f"Available: {sorted(MAPPINGS)}"
        )
    return MAPPINGS[key]
