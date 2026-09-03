"""
Citation Manager — tracks verified sources and maps them to IEEE citation numbers.
Ensures every citation in the paper corresponds to a real, retrieved source.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from app.schemas.research import Citation, SourceRecord

logger = logging.getLogger(__name__)


class CitationManager:
    """
    Manages citations for a research paper.
    Maintains a numbered citation list where each number corresponds to a real source.
    Prevents duplicate citations and ensures all references are verified.
    """

    def __init__(self):
        self._citations: list[Citation] = []
        self._title_to_number: dict[str, int] = {}
        self._next_number: int = 1

    def register_source(self, source: SourceRecord) -> int:
        """
        Register a verified source and return its citation number.
        If the source is already registered (by title), returns the existing number.
        """
        title_key = source.title.strip().lower()
        if title_key in self._title_to_number:
            return self._title_to_number[title_key]

        number = self._next_number
        self._next_number += 1

        citation = Citation(number=number, source=source)
        self._citations.append(citation)
        self._title_to_number[title_key] = number

        logger.debug(f"Registered citation [{number}]: {source.title}")
        return number

    def register_sources_from_list(self, sources: list[dict]) -> dict[str, int]:
        """
        Register multiple sources from a list of dicts.
        Returns a mapping of title -> citation number for use in LLM prompts.
        """
        citation_map: dict[str, int] = {}
        for src_dict in sources:
            source = SourceRecord(
                title=src_dict.get("title", "Unknown Title"),
                authors=src_dict.get("authors", []),
                year=str(src_dict.get("year", "")) if src_dict.get("year") else None,
                source=src_dict.get("source", ""),
                url=src_dict.get("url", src_dict.get("source_url")),
                doi=src_dict.get("doi"),
                abstract=src_dict.get("abstract", src_dict.get("text", ""))[:500],
            )
            num = self.register_source(source)
            citation_map[source.title] = num
        return citation_map

    def get_citation_number(self, title: str) -> Optional[int]:
        """Get the citation number for a source by title."""
        return self._title_to_number.get(title.strip().lower())

    def get_inline_citation(self, identifier: str | int) -> Optional[str]:
        """Get inline citation string like '[1]' for a source title or citation number."""
        if isinstance(identifier, int):
            return f"[{identifier}]"
        num = self.get_citation_number(str(identifier))
        return f"[{num}]" if num else None


    def get_all_citations(self) -> list[Citation]:
        """Return all registered citations, sorted by number."""
        return sorted(self._citations, key=lambda c: c.number)

    def get_reference_list(self) -> list[str]:
        """Return formatted IEEE reference list entries."""
        return [c.ieee_reference_string() for c in self.get_all_citations()]

    def get_reference_list_text(self) -> str:
        """Return the IEEE reference list as a formatted text block."""
        refs = self.get_reference_list()
        return "\n".join(refs)

    def get_citation_map_for_llm(self) -> dict[str, int]:
        """Return title -> number mapping for use in LLM prompts."""
        return {title: num for title, num in self._title_to_number.items()}

    @property
    def count(self) -> int:
        """Number of registered citations."""
        return len(self._citations)

    def validate_citations_in_text(self, text: str) -> tuple[list[int], list[int]]:
        """
        Check which citation numbers in the text are:
        - valid (correspond to registered sources)
        - invalid (not registered — potential hallucinations)
        Returns (valid_numbers, invalid_numbers).
        """
        cited_numbers = [int(m) for m in re.findall(r'\[(\d+)\]', text)]
        valid_citation_numbers = {c.number for c in self._citations}

        valid = [n for n in cited_numbers if n in valid_citation_numbers]
        invalid = [n for n in cited_numbers if n not in valid_citation_numbers]

        return valid, invalid

    def clean_invalid_citations(self, text: str) -> str:
        """
        Remove citation numbers from text that don't correspond to registered sources.
        Replaces invalid [N] with empty string.
        """
        valid_citation_numbers = {c.number for c in self._citations}

        def replace_citation(m):
            num = int(m.group(1))
            return f"[{num}]" if num in valid_citation_numbers else ""

        cleaned = re.sub(r'\[(\d+)\]', replace_citation, text)
        return cleaned


def build_citation_manager_from_online_candidates(candidates: list[dict]) -> CitationManager:
    """
    Build a CitationManager from the online retriever candidate format.
    Each candidate dict has: doc_id, title, author, source, text (abstract).
    """
    manager = CitationManager()
    for cand in candidates:
        # Parse author or authors field
        author_val = cand.get("authors") or cand.get("author") or []
        if isinstance(author_val, str):
            authors = [a.strip() for a in author_val.split(",") if a.strip()]
        elif isinstance(author_val, list):
            authors = [str(a).strip() for a in author_val if a]
        else:
            authors = []

        # Extract year from year field or source string
        year = str(cand.get("year", "")) if cand.get("year") else None
        source_str = cand.get("source", "")
        import re as _re
        if not year and source_str:
            year_match = _re.search(r'\b(19|20)\d{2}\b', source_str)
            if year_match:
                year = year_match.group(0)

        # Extract URL
        url = cand.get("url") or cand.get("source_url")
        if not url and source_str:
            url_match = _re.search(r'https?://[^\s)]+', source_str)
            if url_match:
                url = url_match.group(0)

        source = SourceRecord(
            title=cand.get("title", ""),
            authors=authors,
            year=year,
            source=source_str,
            url=url,
            abstract=(cand.get("abstract", "") or cand.get("text", "") or "")[:500],
        )
        manager.register_source(source)


    return manager
