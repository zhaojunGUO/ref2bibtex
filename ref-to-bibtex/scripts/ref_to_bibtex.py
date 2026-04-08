#!/usr/bin/env python3
"""Convert formatted reference text to BibTeX via title search (DBLP / Crossref / Scholar)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from datetime import datetime
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

import requests


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class SearchResult:
    source: str
    title: str
    bibtex: str


def clean_title(text: str) -> str:
    # Trim common trailing punctuation that appears around quoted titles in references.
    return text.strip().strip(" \t\r\n.,;:!?\"'“”‘’()[]{}")


def is_weak_title(text: str) -> bool:
    t = clean_title(text)
    words = re.findall(r"[A-Za-z0-9]+", t)
    if len(t) < 18 or len(words) < 4:
        return True
    # Typical false positives from author abbreviations, e.g. "Li, S"
    if re.fullmatch(r"[A-Z][a-z]+,\s*[A-Z](?:\.)?", t):
        return True
    return False


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def extract_title(reference: str) -> str:
    ref = reference.strip()

    # remove common leading index marker: [12], (12)
    ref = re.sub(r"^\s*[\[(]?\d+[\])\.]?\s*", "", ref)

    quote_patterns = [
        r'"([^"]+)"',
        r"“([^”]+)”",
    ]
    for pattern in quote_patterns:
        match = re.search(pattern, ref)
        if match:
            return clean_title(match.group(1))

    # Fallback heuristic: choose the longest segment that looks like a paper title.
    segments = [seg.strip() for seg in ref.split(".") if seg.strip()]
    candidates = []
    for segment in segments:
        candidate = clean_title(re.sub(r"^[\d\[\]\s]+", "", segment))
        if not candidate:
            continue
        words = re.findall(r"[A-Za-z0-9]+", candidate)
        if len(words) >= 4:
            candidates.append(candidate)

    if candidates:
        return sorted(candidates, key=len, reverse=True)[0]

    raise ValueError("Unable to extract title from reference. Please provide --title explicitly.")


def fetch_dblp_bibtex(title: str, timeout: float = 15.0) -> Optional[SearchResult]:
    params = {"q": title, "format": "json", "h": 10}
    resp = requests.get("https://dblp.org/search/publ/api", params=params, timeout=timeout)
    resp.raise_for_status()

    payload = resp.json()
    hits = payload.get("result", {}).get("hits", {}).get("hit", [])
    if isinstance(hits, dict):
        hits = [hits]

    best = None
    best_score = -1.0

    for hit in hits:
        info = hit.get("info", {})
        candidate_title = info.get("title", "")
        candidate_key = info.get("key", "")
        if not candidate_title or not candidate_key:
            continue

        score = similarity(title, candidate_title)
        if score > best_score:
            best_score = score
            best = (candidate_title, candidate_key)

    if not best or best_score < 0.72:
        return None

    candidate_title, candidate_key = best
    bib_url = f"https://dblp.org/rec/{candidate_key}.bib"
    bib_resp = requests.get(bib_url, timeout=timeout)
    bib_resp.raise_for_status()
    bibtex = bib_resp.text.strip()

    if not bibtex.startswith("@"):
        return None

    return SearchResult(source="dblp", title=candidate_title, bibtex=bibtex)


def _crossref_year(item: dict) -> str:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and isinstance(parts, list) and parts[0]:
            year = parts[0][0]
            if year:
                return str(year)
    return str(datetime.now().year)


def _crossref_authors(item: dict) -> str:
    authors = item.get("author", [])
    names = []
    for author in authors:
        family = author.get("family", "").strip()
        given = author.get("given", "").strip()
        if family and given:
            names.append(f"{family}, {given}")
        elif family:
            names.append(family)
        elif given:
            names.append(given)
    return " and ".join(names) if names else "Unknown"


def _safe_key_piece(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "", text)
    return text[:24] if text else "paper"


def _build_crossref_bibtex(item: dict) -> str:
    title = clean_title((item.get("title") or ["Untitled"])[0])
    container = (item.get("container-title") or [""])[0]
    volume = item.get("volume", "")
    number = item.get("issue", "")
    pages = item.get("page", "")
    doi = item.get("DOI", "")
    year = _crossref_year(item)
    authors = _crossref_authors(item)
    entry_type = "article" if container else "misc"
    key = f"{_safe_key_piece(authors.split(' and ')[0].split(',')[0])}{year}{_safe_key_piece(title)[:12]}"

    lines = [f"@{entry_type}{{{key},", f"  title = {{{title}}},", f"  author = {{{authors}}},", f"  year = {{{year}}},"]
    if container:
        lines.append(f"  journal = {{{container}}},")
    if volume:
        lines.append(f"  volume = {{{volume}}},")
    if number:
        lines.append(f"  number = {{{number}}},")
    if pages:
        lines.append(f"  pages = {{{pages}}},")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    lines.append("}")
    return "\n".join(lines)


def fetch_crossref_bibtex(title: str, timeout: float = 15.0) -> Optional[SearchResult]:
    params = {"query.title": title, "rows": 10}
    headers = {"User-Agent": UA}
    resp = requests.get("https://api.crossref.org/works", params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()

    items = resp.json().get("message", {}).get("items", [])
    if not items:
        return None

    best_item = None
    best_title = ""
    best_score = -1.0
    for item in items:
        candidate_title = clean_title((item.get("title") or [""])[0])
        if not candidate_title:
            continue
        score = similarity(title, candidate_title)
        if score > best_score:
            best_score = score
            best_title = candidate_title
            best_item = item

    if not best_item or best_score < 0.48:
        return None

    doi = best_item.get("DOI", "")
    if doi:
        try:
            bib_resp = requests.get(
                f"https://doi.org/{doi}",
                headers={"Accept": "application/x-bibtex", "User-Agent": UA},
                timeout=timeout,
            )
            bib_resp.raise_for_status()
            bibtex = bib_resp.text.strip()
            if bibtex.startswith("@"):
                return SearchResult(source="crossref", title=best_title, bibtex=bibtex)
        except Exception:
            pass

    return SearchResult(source="crossref", title=best_title, bibtex=_build_crossref_bibtex(best_item))


def fetch_crossref_bibtex_by_reference(reference: str, timeout: float = 15.0) -> Optional[SearchResult]:
    params = {"query.bibliographic": reference, "rows": 10}
    headers = {"User-Agent": UA}
    resp = requests.get("https://api.crossref.org/works", params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()

    items = resp.json().get("message", {}).get("items", [])
    if not items:
        return None

    ref_norm = normalize_text(reference)
    best_item = None
    best_title = ""
    best_score = -1.0

    for item in items:
        candidate_title = clean_title((item.get("title") or [""])[0])
        if not candidate_title:
            continue
        container = clean_title((item.get("container-title") or [""])[0])
        year = _crossref_year(item)
        authors = _crossref_authors(item)
        compound = f"{authors}. {candidate_title}. {container}. {year}"
        score = similarity(ref_norm, compound)
        if score > best_score:
            best_score = score
            best_title = candidate_title
            best_item = item

    if not best_item or best_score < 0.18:
        return None

    doi = best_item.get("DOI", "")
    if doi:
        try:
            bib_resp = requests.get(
                f"https://doi.org/{doi}",
                headers={"Accept": "application/x-bibtex", "User-Agent": UA},
                timeout=timeout,
            )
            bib_resp.raise_for_status()
            bibtex = bib_resp.text.strip()
            if bibtex.startswith("@"):
                return SearchResult(source="crossref", title=best_title, bibtex=bibtex)
        except Exception:
            pass

    return SearchResult(source="crossref", title=best_title, bibtex=_build_crossref_bibtex(best_item))


def _extract_scholar_bibtex_link(result_block) -> Optional[str]:
    for link in result_block.select("div.gs_fl a"):
        text = link.get_text(" ", strip=True).lower()
        href = link.get("href", "")
        if ("bibtex" in text or "output=cite" in href) and href:
            return urllib.parse.urljoin("https://scholar.google.com", href)
    return None


def _resolve_scholar_cite_to_bibtex(cite_url: str, headers: dict, timeout: float) -> Optional[str]:
    # Scholar result footers usually expose "Cite", then BibTeX is inside that page.
    from bs4 import BeautifulSoup

    cite_resp = requests.get(cite_url, headers=headers, timeout=timeout)
    cite_resp.raise_for_status()
    cite_soup = BeautifulSoup(cite_resp.text, "html.parser")

    for link in cite_soup.select("a"):
        href = link.get("href", "")
        text = link.get_text(" ", strip=True).lower()
        if "bibtex" in text or "scholar.bib" in href:
            return urllib.parse.urljoin("https://scholar.google.com", href)
    return None


def fetch_google_scholar_bibtex(title: str, timeout: float = 20.0) -> Optional[SearchResult]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 is required for Google Scholar source. Install from requirements.txt.") from exc

    headers = {"User-Agent": UA}
    queries = [f'intitle:"{title}"', f'"{title}"', title]

    best_link = None
    best_title = ""
    best_score = -1.0

    for query in queries:
        params = {"q": query, "hl": "en"}
        resp = requests.get("https://scholar.google.com/scholar", params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()

        html = resp.text
        if "unusual traffic" in html.lower() or "not a robot" in html.lower():
            return None

        soup = BeautifulSoup(html, "html.parser")
        results = soup.select("div.gs_ri")
        if not results:
            continue

        for block in results:
            title_elem = block.select_one("h3.gs_rt")
            if not title_elem:
                continue
            candidate_title = clean_title(title_elem.get_text(" ", strip=True))
            score = similarity(title, candidate_title)
            bib_link = _extract_scholar_bibtex_link(block)
            if bib_link and score > best_score:
                best_score = score
                best_link = bib_link
                best_title = candidate_title

        if best_link and best_score >= 0.55:
            break

    if not best_link or best_score < 0.55:
        return None

    if "output=cite" in best_link:
        resolved = _resolve_scholar_cite_to_bibtex(best_link, headers=headers, timeout=timeout)
        if not resolved:
            return None
        best_link = resolved

    bib_resp = requests.get(best_link, headers=headers, timeout=timeout)
    bib_resp.raise_for_status()
    bibtex = bib_resp.text.strip()

    if not bibtex.startswith("@"):
        return None

    return SearchResult(source="google_scholar", title=best_title, bibtex=bibtex)


def resolve_bibtex(title: str, source: str, timeout: float, reference_text: str = "") -> SearchResult:
    errors = []
    weak_title = is_weak_title(title)

    # For weakly extracted titles (e.g. "Li, S"), prefer full-reference matching first.
    if source == "auto" and reference_text and weak_title:
        try:
            result = fetch_crossref_bibtex_by_reference(reference=reference_text, timeout=timeout)
            if result:
                return result
        except Exception as exc:  # pragma: no cover - network variability
            errors.append(f"Crossref(biblio-first) failed: {exc}")

    if source in {"auto", "dblp"}:
        try:
            result = fetch_dblp_bibtex(title=title, timeout=timeout)
            if result:
                return result
        except Exception as exc:  # pragma: no cover - network variability
            errors.append(f"DBLP failed: {exc}")

    if source in {"auto", "crossref"}:
        try:
            result = fetch_crossref_bibtex(title=title, timeout=timeout)
            if result:
                return result
        except Exception as exc:  # pragma: no cover - network variability
            errors.append(f"Crossref failed: {exc}")

        if reference_text:
            try:
                result = fetch_crossref_bibtex_by_reference(reference=reference_text, timeout=timeout)
                if result:
                    return result
            except Exception as exc:  # pragma: no cover - network variability
                errors.append(f"Crossref(biblio) failed: {exc}")

    if source in {"auto", "scholar"}:
        try:
            result = fetch_google_scholar_bibtex(title=title, timeout=timeout)
            if result:
                return result
        except Exception as exc:  # pragma: no cover - network variability
            errors.append(f"Google Scholar failed: {exc}")

    detail = " | ".join(errors) if errors else "No matching paper found."
    raise RuntimeError(f"Unable to resolve BibTeX for title '{title}'. {detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract title from reference text and fetch BibTeX from DBLP/Crossref/Google Scholar."
    )
    parser.add_argument("--reference", "-r", help="Reference text in free-form citation style.")
    parser.add_argument("--title", help="Explicit title (skip title extraction from reference).")
    parser.add_argument(
        "--source",
        choices=["auto", "dblp", "crossref", "scholar"],
        default="auto",
        help="Search source. 'auto' = DBLP, then Crossref, then Google Scholar.",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON payload with title/source/bibtex.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    reference = args.reference
    if not reference and not args.title:
        reference = sys.stdin.read().strip()

    if args.title:
        title = clean_title(args.title)
    elif reference:
        title = clean_title(extract_title(reference))
    else:
        print("Error: provide --reference, --title, or stdin reference text.", file=sys.stderr)
        return 2

    try:
        result = resolve_bibtex(title=title, source=args.source, timeout=args.timeout, reference_text=reference or "")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"input_title": title, "matched_title": result.title, "source": result.source, "bibtex": result.bibtex},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(result.bibtex)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
