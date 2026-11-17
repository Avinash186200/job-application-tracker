"""De-duplication: the same role at the same company is one application, however it is spelled.

Two applications are duplicates when their normalised (company, title) keys match, or when both have a URL and the
normalised URLs match. ``near_duplicates`` also flags close spellings (for review, never merged automatically).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlsplit

_TITLE_SYNONYMS = {"sr": "senior", "snr": "senior", "jr": "junior", "mgr": "manager", "eng": "engineer",
                   "engg": "engineer", "dev": "developer", "ml": "machine learning", "ai": "ai"}
_TRACKING_PARAMS = re.compile(r"^(utm_|ref$|src$|source$|trk|gclid|fbclid)")


def _words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    return re.findall(r"[a-z0-9]+", s)


def norm_company(name: str, suffixes: list[str]) -> str:
    words = _words(name)
    while len(words) > 1 and words[-1] in suffixes:
        words.pop()
    return " ".join(words)


def norm_title(title: str) -> str:
    words = []
    for w in _words(title):
        words.extend(_TITLE_SYNONYMS.get(w, w).split())
    return " ".join(words)


def norm_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = "&".join(sorted(q for q in parts.query.split("&") if q and not _TRACKING_PARAMS.match(q.split("=")[0])))
    return f"{host}{parts.path.rstrip('/')}" + (f"?{query}" if query else "")


def key(company: str, title: str, suffixes: list[str]) -> str:
    return f"{norm_company(company, suffixes)}|{norm_title(title)}"


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def near_duplicates(k: str, existing: list[tuple[int, str]], threshold: float = 0.9) -> list[int]:
    """Ids whose key is close to ``k`` but not equal: likely the same role, spelled differently."""
    return [i for i, other in existing if other != k and similarity(k, other) >= threshold]
