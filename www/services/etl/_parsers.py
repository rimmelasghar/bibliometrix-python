from __future__ import annotations

import re
from typing import Any, Dict, List


# --------------------------------------------------------------------------- #
#  WEB OF SCIENCE (.txt / .ciw)                                               #
# --------------------------------------------------------------------------- #

def parse_wos_data(datapath: str) -> List[Dict[str, Any]]:
    elem_data: List[Dict[str, Any]] = []
    data: Dict[str, Any] = {}
    current_key = None

    with open(datapath, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    for line in lines[2:]:
        line = line.rstrip()
        if line.strip() not in (" ", "EF", ""):
            if line.startswith("ER"):
                elem_data.append(data.copy())
                current_key = None
                data = {}
            elif line.startswith("  "):
                if current_key:
                    if current_key in data:
                        if current_key in {"DE", "C3", "EM", "FU", "FX", "WC"}:
                            joined = " ".join(data[current_key]) + " " + line.strip()
                            data[current_key] = [joined]
                        else:
                            data[current_key].append(line.strip())
                    else:
                        data[current_key] = [line.strip()]
            else:
                line = line.strip()
                key_value = line.split(" ", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    data[key] = [value]
                    current_key = key
        elif line.strip() == "":
            continue
    return elem_data


# --------------------------------------------------------------------------- #
#  PUBMED MEDLINE plain-text                                                  #
# --------------------------------------------------------------------------- #

_PUBMED_KEY = re.compile(r"^([A-Z]+)\s*-\s*(.+)")


def parse_pubmed_data(datapath: str) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    last_key: str | None = None

    with open(datapath, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    for line in lines:
        if not line.strip():
            if current:
                data.append(current)
                current = {}
                last_key = None
            continue
        m = _PUBMED_KEY.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if key in current:
                current[key] += ";" + value
            else:
                current[key] = value
            last_key = key
        elif last_key is not None:
            current[last_key] += " " + line.strip()
    if current:
        data.append(current)
    return data


# --------------------------------------------------------------------------- #
#  COCHRANE plain-text                                                        #
# --------------------------------------------------------------------------- #

_COCHRANE_KEY = re.compile(r"^([A-Z]{2,})\s*:\s*(.+)")


def parse_cochrane_data(datapath: str) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    last_key: str | None = None

    with open(datapath, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    for raw in lines:
        line = raw.strip()
        if not line:
            if current:
                current.pop("Record", None)
                if current.get("AB", "").startswith("Abstract - Background"):
                    current["AB"] = current["AB"][22:].strip()
                data.append(current)
                current = {}
                last_key = None
            continue
        if line.startswith("Record #"):
            if current:
                current.pop("Record", None)
                data.append(current)
                current = {}
                last_key = None
            continue
        m = _COCHRANE_KEY.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if key in current:
                current[key] += "; " + value
            else:
                current[key] = value
            last_key = key
        elif last_key is not None:
            current[last_key] += " " + line
    if current:
        current.pop("Record", None)
        data.append(current)
    return data
