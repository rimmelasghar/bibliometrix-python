from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional

import requests

from .standardizer import convert2df


_DEFAULT_TIMEOUT = 30  # seconds


# --------------------------------------------------------------------------- #
#  RETRY / BACK-OFF                                                           #
# --------------------------------------------------------------------------- #

def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
    timeout: int = _DEFAULT_TIMEOUT,
    max_retries: int = 5,
    min_sleep: float = 0.34,
) -> requests.Response:
    """HTTP request with exponential back-off and ``Retry-After`` support."""
    backoff = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = session.request(
                method, url,
                params=params, headers=headers, data=data,
                timeout=timeout,
            )
            if resp.status_code in (429, 502, 503, 504):
                wait = float(resp.headers.get("Retry-After", backoff))
                time.sleep(max(wait, min_sleep))
                backoff = min(backoff * 2, 30)
                continue
            resp.raise_for_status()
            # polite floor between successful calls
            time.sleep(min_sleep)
            return resp
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    raise RuntimeError(
        f"HTTP request to {url} failed after {max_retries} retries"
    ) from last_exc


# --------------------------------------------------------------------------- #
#  OPENALEX                                                                   #
# --------------------------------------------------------------------------- #

OPENALEX_BASE = "https://api.openalex.org/works"


def fetch_openalex(
    query: str,
    *,
    max_results: int = 200,
    per_page: int = 200,
    mailto: Optional[str] = None,
    extra_filters: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """Retrieve OpenAlex *works* matching ``query``.

    Parameters
    ----------
    query : str
        Free-text query (matched against title, abstract and full text).
    max_results : int
        Cap on the number of records returned.  OpenAlex caps ``per_page``
        at 200.
    per_page : int
        Page size (1–200).
    mailto : str, optional
        Adds the caller to OpenAlex's *polite pool* (faster, more reliable).
    extra_filters : dict, optional
        Additional ``filter=`` clauses (joined with ``,``).  Example::

            extra_filters={"from_publication_date": "2020-01-01"}
    """
    sess = session or requests.Session()
    per_page = max(1, min(per_page, 200))

    params: Dict[str, Any] = {
        "search": query,
        "per-page": per_page,
        "cursor": "*",
    }
    if mailto:
        params["mailto"] = mailto
    if extra_filters:
        params["filter"] = ",".join(f"{k}:{v}" for k, v in extra_filters.items())

    headers = {"User-Agent": f"bibliometrix-python-etl ({mailto or 'no-mail'})"}

    out: List[Dict[str, Any]] = []
    while True:
        resp = _request_with_retry(sess, "GET", OPENALEX_BASE,
                                   params=params, headers=headers,
                                   min_sleep=0.1)
        payload = resp.json()
        results = payload.get("results") or []
        out.extend(results)
        if len(out) >= max_results:
            out = out[:max_results]
            break
        next_cursor = (payload.get("meta") or {}).get("next_cursor")
        if not next_cursor or not results:
            break
        params["cursor"] = next_cursor

    return out


# --------------------------------------------------------------------------- #
#  PUBMED (E-utilities)                                                       #
# --------------------------------------------------------------------------- #

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _pubmed_min_sleep(api_key: Optional[str]) -> float:
    """Without API key: 3 req/s.  With API key: 10 req/s."""
    return 0.11 if api_key else 0.34


def fetch_pubmed(
    query: str,
    *,
    max_results: int = 200,
    batch_size: int = 200,
    api_key: Optional[str] = None,
    email: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """Retrieve PubMed records matching ``query`` via E-utilities.

    Returns
    -------
    list[dict]
        Each dict has the same shape produced by
        :func:`www.services.parsers.parse_pubmed_data` so the existing
        ``MAPPINGS["pubmed_txt"]`` mapping can be reused unchanged.
    """
    sess = session or requests.Session()
    min_sleep = _pubmed_min_sleep(api_key)

    # ---- esearch: collect PMIDs (history server via usehistory=y) ------ #
    s_params: Dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmax": min(batch_size, max_results),
        "usehistory": "y",
        "retmode": "json",
    }
    if api_key:
        s_params["api_key"] = api_key
    if email:
        s_params["email"] = email

    resp = _request_with_retry(sess, "GET", ESEARCH_URL,
                               params=s_params, min_sleep=min_sleep)
    esearch = resp.json().get("esearchresult", {})
    webenv = esearch.get("webenv")
    query_key = esearch.get("querykey")
    total = int(esearch.get("count", 0))
    n = min(total, max_results)

    out: List[Dict[str, Any]] = []
    fetched = 0
    while fetched < n:
        f_params: Dict[str, Any] = {
            "db": "pubmed",
            "WebEnv": webenv,
            "query_key": query_key,
            "retstart": fetched,
            "retmax": min(batch_size, n - fetched),
            "retmode": "xml",
            "rettype": "medline",
        }
        if api_key:
            f_params["api_key"] = api_key
        if email:
            f_params["email"] = email

        resp = _request_with_retry(sess, "GET", EFETCH_URL,
                                   params=f_params, min_sleep=min_sleep)
        batch = _parse_pubmed_xml(resp.content)
        if not batch:
            break
        out.extend(batch)
        fetched += len(batch)

    return out[:max_results]


# --------------------------------------------------------------------------- #
#  PUBMED XML → MEDLINE-style dict                                            #
# --------------------------------------------------------------------------- #

def _t(node: Optional[ET.Element]) -> str:
    return (node.text or "").strip() if node is not None and node.text else ""


def _join_text(node: Optional[ET.Element]) -> str:
    """Recursively collect text from <AbstractText> blocks that may contain
    inline tags (<sup>, <i>, etc.)."""
    if node is None:
        return ""
    return " ".join(t.strip() for t in node.itertext() if t and t.strip())


def _parse_pubmed_xml(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Convert an efetch XML payload to records mimicking the MEDLINE
    plain-text parser output (semicolon-joined multi-value fields)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    records: List[Dict[str, Any]] = []
    for art in root.findall(".//PubmedArticle"):
        med = art.find("MedlineCitation") or art
        article = med.find("Article")
        rec: Dict[str, Any] = {}

        rec["PMID"] = _t(med.find("PMID"))
        rec["TI"]   = _t(article.find("ArticleTitle")) if article is not None else ""

        # Abstract — concatenate <AbstractText> children
        abst_parts: List[str] = []
        if article is not None:
            for abst in article.findall("./Abstract/AbstractText"):
                label = abst.attrib.get("Label")
                txt = _join_text(abst)
                if label:
                    abst_parts.append(f"{label}: {txt}")
                else:
                    abst_parts.append(txt)
        rec["AB"] = " ".join(p for p in abst_parts if p)

        # Authors (initials form  + full names + affiliations)
        au_list, fau_list, ad_list = [], [], []
        if article is not None:
            for au in article.findall("./AuthorList/Author"):
                last = _t(au.find("LastName"))
                first = _t(au.find("ForeName"))
                init = _t(au.find("Initials"))
                if last:
                    au_list.append(f"{last} {init}".strip())
                    if first:
                        fau_list.append(f"{last}, {first}")
                    else:
                        fau_list.append(last)
                for aff in au.findall("./AffiliationInfo/Affiliation"):
                    if aff.text:
                        ad_list.append(aff.text.strip())
        rec["AU"]  = ";".join(au_list)
        rec["FAU"] = ";".join(fau_list)
        rec["AD"]  = ";".join(ad_list)

        # Journal info
        if article is not None:
            jrn = article.find("Journal")
            if jrn is not None:
                rec["JT"] = _t(jrn.find("Title"))
                rec["TA"] = _t(jrn.find("ISOAbbreviation"))
                iss = jrn.find("./JournalIssue/PubDate/Year")
                if iss is not None and iss.text:
                    rec["DP"] = iss.text.strip()
                else:
                    md = jrn.find("./JournalIssue/PubDate/MedlineDate")
                    rec["DP"] = _t(md)
                rec["VI"] = _t(jrn.find("./JournalIssue/Volume"))
                rec["IP"] = _t(jrn.find("./JournalIssue/Issue"))
                rec["IS"] = _t(jrn.find("./ISSN"))
            rec["PG"] = _t(article.find("./Pagination/MedlinePgn"))
            rec["LA"] = _t(article.find("./Language"))
            rec["PT"] = ";".join(_t(p) for p in article.findall("./PublicationTypeList/PublicationType"))

        # DOI / LID
        if article is not None:
            for elid in article.findall("./ELocationID"):
                if elid.attrib.get("EIdType") == "doi" and elid.text:
                    rec["LID"] = f"{elid.text.strip()} [doi]"
                    break

        # MeSH terms
        mh = []
        for mh_node in med.findall("./MeshHeadingList/MeshHeading/DescriptorName"):
            t = (mh_node.text or "").strip()
            if mh_node.attrib.get("MajorTopicYN") == "Y":
                t = f"*{t}"
            if t:
                mh.append(t)
        rec["MH"] = ";".join(mh)

        # Other keywords
        rec["OT"] = ";".join(
            _t(k) for k in med.findall("./KeywordList/Keyword") if _t(k)
        )

        records.append(rec)
    return records


# --------------------------------------------------------------------------- #
#  ONE-CALL CONVENIENCE                                                       #
# --------------------------------------------------------------------------- #

def fetch_dataframe(
    source: str,
    query: str,
    *,
    max_results: int = 200,
    **kwargs: Any,
):
    """Single-call helper: query the API and return a standardised DataFrame.

    Equivalent to ``convert2df(source, records=fetch_<source>(...))``.
    """
    src = source.lower()
    if src == "openalex":
        recs = fetch_openalex(query, max_results=max_results, **kwargs)
    elif src == "pubmed":
        recs = fetch_pubmed(query, max_results=max_results, **kwargs)
    else:
        raise ValueError(
            f"fetch_dataframe: unsupported API source '{source}'. "
            "Use 'openalex' or 'pubmed'."
        )
    return convert2df(source=src, records=recs)
