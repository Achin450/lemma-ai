"""
Citation Parser Service

Parses in-text citations and bibliography entries from academic documents.
Supports APA, MLA, Chicago, and IEEE citation formats.
"""
from __future__ import annotations
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Regex patterns for in-text citations
CITATION_PATTERNS = [
    # APA: (Author, Year) or (Author & Author, Year)
    (r"\(([A-Z][a-zA-Z'\-]+(?:\s*[&,]\s*[A-Z][a-zA-Z'\-]+)*,\s*\d{4}[a-z]?)\)", "apa"),
    # APA et al.: (Author et al., Year)
    (r"\(([A-Z][a-zA-Z'\-]+\s+et\s+al\.?,\s*\d{4}[a-z]?)\)", "apa"),
    # IEEE: [1] or [1, 2] or [1-3]
    (r"\[(\d+(?:[,\s\-]+\d+)*)\]", "ieee"),
    # MLA: (Author Page) or (Author)
    (r"\(([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?\s+\d+)\)", "mla"),
    # Footnote/endnote: superscript numbers
    (r"(?<=[\w,\.])([¹²³⁴⁵⁶⁷⁸⁹]|\^\d+)", "footnote"),
]

# Patterns to detect bibliography sections
BIBLIO_SECTION_HEADERS = [
    r"^\s*references?\s*$",
    r"^\s*bibliography\s*$",
    r"^\s*works?\s+cited\s*$",
    r"^\s*sources?\s*$",
    r"^\s*literature\s+cited\s*$",
]


class CitationParserService:
    """Parses citations and bibliography from document text."""

    @classmethod
    def extract_in_text_citations(cls, text: str) -> list[dict]:
        """
        Find all in-text citations in the document.
        Returns list of dicts with {text, style, author, year, start_char, end_char}.
        """
        citations = []
        seen_spans = set()

        for pattern, style in CITATION_PATTERNS:
            for match in re.finditer(pattern, text):
                span = (match.start(), match.end())
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                cit_text = match.group(0)
                author, year, ref_num = None, None, None

                if style == "apa":
                    inner = match.group(1)
                    parts = inner.rsplit(",", 1)
                    author = parts[0].strip() if len(parts) > 1 else inner
                    year = parts[1].strip() if len(parts) > 1 else None
                elif style == "ieee":
                    try:
                        # Take first number
                        ref_num = int(re.findall(r"\d+", match.group(1))[0])
                    except Exception:
                        pass
                elif style == "mla":
                    inner = match.group(1)
                    parts = inner.rsplit(" ", 1)
                    author = parts[0].strip() if parts else inner

                # Find surrounding sentence
                sent_start = max(0, match.start() - 200)
                sent_end = min(len(text), match.end() + 200)
                context = text[sent_start:sent_end].replace("\n", " ")

                citations.append({
                    "text": cit_text,
                    "style": style,
                    "author": author,
                    "year": year,
                    "reference_number": ref_num,
                    "sentence_context": context,
                    "start_char": match.start(),
                    "end_char": match.end(),
                })

        # Sort by position
        citations.sort(key=lambda x: x["start_char"])
        return citations

    @classmethod
    def extract_bibliography(cls, text: str) -> list[dict]:
        """
        Extract bibliography entries from the references section of the text.
        Returns list of dicts with {raw_text, author, title, year}.
        """
        # Find the bibliography section start
        biblio_start = None
        lines = text.split("\n")
        for i, line in enumerate(lines):
            for header_pat in BIBLIO_SECTION_HEADERS:
                if re.match(header_pat, line.strip(), re.IGNORECASE):
                    biblio_start = i + 1
                    break
            if biblio_start is not None:
                break

        if biblio_start is None:
            # Try to detect by looking for dense citation-like text in last 25% of document
            cutoff = int(len(lines) * 0.75)
            biblio_start = cutoff

        biblio_lines = lines[biblio_start:]
        biblio_text = "\n".join(biblio_lines).strip()

        if not biblio_text:
            return []

        # Split entries: each entry typically starts at the beginning of a line
        # or with a number [1] for IEEE
        entries_raw = []

        # IEEE-style numbered
        if re.search(r"^\[\d+\]", biblio_text, re.MULTILINE):
            entries_raw = re.split(r"(?=^\[\d+\])", biblio_text, flags=re.MULTILINE)
        else:
            # Paragraph-separated entries
            entries_raw = re.split(r"\n{2,}", biblio_text)

        entries = []
        for raw in entries_raw:
            raw = raw.strip()
            if not raw or len(raw) < 10:
                continue

            author, title, year = None, None, None

            # Try to extract year
            year_match = re.search(r"\b(19|20)\d{2}\b", raw)
            if year_match:
                year = year_match.group(0)

            # Try to extract author (first element before year or comma)
            author_match = re.match(r"^([A-Z][a-zA-Z'\-]+(?:,\s*[A-Z][a-zA-Z.]+)?)", raw)
            if author_match:
                author = author_match.group(1)

            # Try to extract title (quoted or in italics-like format)
            title_match = re.search(r'"([^"]{10,})"|\u201c([^\u201d]{10,})\u201d', raw)
            if title_match:
                title = (title_match.group(1) or title_match.group(2)).strip()

            entries.append({
                "raw_text": raw,
                "author": author,
                "title": title,
                "year": year,
                "cited_in_text": False,
            })

        return entries

    @classmethod
    def cross_reference(cls, citations: list[dict], bibliography: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Cross-reference in-text citations against bibliography entries.
        Marks bibliography entries as 'cited_in_text' and returns
        (updated_citations, updated_bibliography).
        """
        for cit in citations:
            cit_author = (cit.get("author") or "").lower()
            cit_year = cit.get("year") or ""
            ref_num = cit.get("reference_number")

            for bib in bibliography:
                bib_author = (bib.get("author") or "").lower()
                bib_year = bib.get("year") or ""

                matched = False
                if ref_num is not None:
                    # IEEE: match by position
                    bib_num_match = re.match(r"\[(\d+)\]", bib["raw_text"])
                    if bib_num_match and int(bib_num_match.group(1)) == ref_num:
                        matched = True
                elif cit_author and bib_author:
                    # Match by author surname (first token)
                    cit_surname = cit_author.split()[0] if cit_author.split() else cit_author
                    bib_surname = bib_author.split()[0] if bib_author.split() else bib_author
                    if cit_surname and bib_surname and cit_surname in bib_surname:
                        if not cit_year or cit_year == bib_year:
                            matched = True

                if matched:
                    bib["cited_in_text"] = True
                    break

        return citations, bibliography
