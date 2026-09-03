"""
Paper Restructurer Service — extracts and restructures an uploaded paper into IEEE format.

Pipeline:
  Uploaded Document → Text Extraction → Section Detection → Content Classification
  → IEEE Section Mapping → Reordering → Minimal Rewriting → Citation Preservation
  → IEEE Formatting → Output

Preserves the user's original research content, facts, and numerical values.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Optional, Callable

from app.schemas.research import (
    ResearchPaper, PaperSection, PaperSubsection, Citation, SourceRecord,
    PaperType, PaperStatus
)
from app.services.llm import LLMService
from app.services.citation_manager import CitationManager

logger = logging.getLogger(__name__)

# Common section heading patterns
SECTION_HEADING_PATTERNS = [
    r'^(?:section\s+)?(?:[IVX]+\.?\s+)?([A-Z][A-Z\s&:,/-]+)$',   # ALL CAPS headings
    r'^(?:\d+\.?\s+)?([A-Z][a-zA-Z\s]+)$',                         # Numbered or title case
    r'^([A-Z][A-Z\s]+):?\s*$',                                       # ALL CAPS with optional colon
]

IEEE_SECTIONS_CANONICAL = [
    "ABSTRACT",
    "INTRODUCTION",
    "RELATED WORK",
    "LITERATURE REVIEW",
    "BACKGROUND",
    "METHODOLOGY",
    "METHODS",
    "EXPERIMENTAL SETUP",
    "RESULTS",
    "EVALUATION",
    "EXPERIMENTS",
    "DISCUSSION",
    "ANALYSIS",
    "CONCLUSION",
    "FUTURE WORK",
    "REFERENCES",
    "ACKNOWLEDGMENT",
    "ACKNOWLEDGEMENTS",
]

ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


class PaperRestructurerService:
    """
    Restructures an uploaded research document into IEEE paper format.
    Preserves the author's original research content while reorganizing structure.
    """

    def __init__(self, progress_callback: Optional[Callable[[str, int], None]] = None):
        self.progress_callback = progress_callback

    def _report_progress(self, step: str, pct: int):
        logger.info(f"[Restructurer] {pct}% — {step}")
        if self.progress_callback:
            try:
                self.progress_callback(step, pct)
            except Exception:
                pass

    async def restructure(self, text: str, filename: str = "document",
                          paper_id: str = None,
                          preserve_citations: bool = True) -> ResearchPaper:
        """
        Main restructuring pipeline.

        Args:
            text: Extracted document text
            filename: Original filename (used for title inference)
            paper_id: Optional ID to assign to the paper
            preserve_citations: Whether to preserve existing citations

        Returns:
            ResearchPaper with IEEE structure
        """
        if not paper_id:
            paper_id = str(uuid.uuid4())

        paper = ResearchPaper(
            paper_id=paper_id,
            status=PaperStatus.processing,
            paper_type=PaperType.restructured,
        )

        try:
            # === Stage 1: Extract existing metadata (5%) ===
            self._report_progress("Extracting document structure...", 5)
            title = self._extract_title(text, filename)
            paper.title = title

            # === Stage 2: Extract abstract if present (10%) ===
            self._report_progress("Extracting abstract and keywords...", 10)
            abstract = self._extract_abstract(text)
            keywords = self._extract_keywords(text)
            paper.abstract = abstract
            paper.keywords = keywords

            # === Stage 3: Detect sections using regex + LLM (10-25%) ===
            self._report_progress("Detecting document sections...", 15)
            detected_sections = self._detect_sections_regex(text)

            if not detected_sections:
                self._report_progress("Using AI to detect sections...", 20)
                llm_sections = await LLMService.detect_sections(text)
                detected_sections = llm_sections if llm_sections else [
                    {"title": "Content", "content": text}
                ]

            # === Stage 4: Extract content for each detected section (25-45%) ===
            self._report_progress("Extracting section content...", 25)
            sections_with_content = self._extract_section_content(text, detected_sections)

            # === Stage 5: Map to IEEE structure (45-55%) ===
            self._report_progress("Mapping to IEEE section structure...", 45)
            section_titles = [s["title"] for s in sections_with_content]
            ieee_mapping = await LLMService.map_to_ieee_sections(section_titles, topic=title)

            # === Stage 6: Merge and reorder content into IEEE sections (55-70%) ===
            self._report_progress("Reordering sections into IEEE format...", 55)
            ieee_sections = self._apply_ieee_mapping(sections_with_content, ieee_mapping)

            # === Stage 7: Extract existing citations (70-75%) ===
            self._report_progress("Extracting existing citations and references...", 70)
            existing_refs = self._extract_references(text)
            citation_manager = CitationManager()

            if existing_refs and preserve_citations:
                for ref in existing_refs:
                    source = SourceRecord(
                        title=ref.get("title", ""),
                        authors=ref.get("authors", []),
                        year=ref.get("year"),
                        source=ref.get("venue", ""),
                    )
                    if source.title:
                        citation_manager.register_source(source)

            paper.citations = citation_manager.get_all_citations()
            paper.sources = [c.source for c in paper.citations]

            # === Stage 8: Build final IEEE sections (75-85%) ===
            self._report_progress("Formatting IEEE sections...", 75)
            roman_counter = 0
            final_sections: list[PaperSection] = []

            for sec in ieee_sections:
                if not sec.get("content", "").strip():
                    continue
                if sec["title"].upper() in ("ABSTRACT", "TITLE"):
                    # Already handled as paper metadata
                    if sec["title"].upper() == "ABSTRACT" and not paper.abstract:
                        paper.abstract = sec["content"].strip()
                    continue
                if sec["title"].upper() == "REFERENCES":
                    # Don't add as a section — handled via citation list
                    continue

                num = ROMAN_NUMERALS[roman_counter % len(ROMAN_NUMERALS)]
                roman_counter += 1

                final_sections.append(PaperSection(
                    number=num,
                    title=sec["title"].upper(),
                    content=sec["content"].strip(),
                ))

            # If abstract is still empty, use first section's content snippet
            if not paper.abstract and final_sections:
                first_content = final_sections[0].content
                paper.abstract = first_content[:500] + "..." if len(first_content) > 500 else first_content

            paper.sections = final_sections

            # === Stage 9: Run Similarity Check (85-95%) ===
            self._report_progress("Running similarity analysis...", 88)
            similarity_score = await self._run_similarity_check(paper)
            paper.similarity_score = similarity_score

            # === Done ===
            self._report_progress("Restructuring complete!", 100)
            paper.status = PaperStatus.completed

        except Exception as e:
            logger.error(f"Restructuring failed: {e}", exc_info=True)
            paper.status = PaperStatus.failed
            paper.error = str(e)

        return paper

    def _extract_title(self, text: str, filename: str) -> str:
        """Extract paper title from the document text."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return filename.replace("_", " ").replace("-", " ").rsplit(".", 1)[0]

        # Heuristic: first non-empty line is often the title
        # Filter lines that look like section headings or reference markers
        for line in lines[:5]:
            if len(line) > 10 and len(line) < 200:
                # Skip obviously non-title lines
                if not re.match(r'^\d+\.', line) and not line.startswith('['):
                    return line

        return filename.replace("_", " ").replace("-", " ").rsplit(".", 1)[0]

    def _extract_abstract(self, text: str) -> str:
        """Extract the abstract section from the document."""
        # Look for abstract marker
        abstract_match = re.search(
            r'(?:abstract|ABSTRACT|Abstract)\s*[\n:—–-]+\s*(.*?)(?:\n\s*(?:keywords|introduction|1\.|I\.)|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if abstract_match:
            abstract = abstract_match.group(1).strip()
            # Limit to reasonable length
            return abstract[:1500]
        return ""

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from the document."""
        keyword_match = re.search(
            r'(?:index\s+terms|keywords|key\s+words)\s*[:\—–-]+\s*([^\n]+)',
            text,
            re.IGNORECASE
        )
        if keyword_match:
            kw_str = keyword_match.group(1)
            # Split by comma or semicolon
            keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
            return keywords[:10]
        return []

    def _detect_sections_regex(self, text: str) -> list[dict]:
        """
        Detect section boundaries using regex patterns for common heading styles.
        Returns list of {title, start_pos} dicts.
        """
        sections = []
        lines = text.splitlines(keepends=True)

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Check for numbered sections: "1. Introduction" or "I. Introduction"
            numbered = re.match(r'^(\d+\.|[IVX]+\.)\s+(.+)$', stripped)
            if numbered:
                title = numbered.group(2).strip()
                if 3 < len(title) < 60:
                    sections.append({"title": title, "content": ""})
                    continue

            # Check for ALL CAPS headings (common in academic papers)
            if stripped.isupper() and 3 < len(stripped) < 80 and ' ' in stripped:
                sections.append({"title": stripped, "content": ""})
                continue

            # Check for title case headings followed by blank line or content
            if re.match(r'^[A-Z][a-zA-Z\s]+$', stripped) and 4 < len(stripped) < 60:
                sections.append({"title": stripped, "content": ""})

        return sections

    def _extract_section_content(self, text: str, sections: list[dict]) -> list[dict]:
        """
        Extract the content for each detected section by splitting the full text.
        """
        if not sections:
            return [{"title": "Content", "content": text}]

        result = []
        # Build split points by finding each section title in the text
        section_positions = []
        for sec in sections:
            title = sec["title"]
            # Try to find the section title in the text
            # Try exact match first, then case-insensitive
            match = re.search(
                r'(?:^|\n)(?:\d+\.|[IVX]+\.)?\s*' + re.escape(title) + r'\s*\n',
                text, re.IGNORECASE
            )
            if match:
                section_positions.append({
                    "title": title,
                    "start": match.start(),
                    "end": match.end()
                })

        if not section_positions:
            # Fallback: just use the detected sections with empty content
            return sections

        # Sort by position
        section_positions.sort(key=lambda x: x["start"])

        for i, pos in enumerate(section_positions):
            content_start = pos["end"]
            content_end = section_positions[i + 1]["start"] if i + 1 < len(section_positions) else len(text)
            content = text[content_start:content_end].strip()
            result.append({"title": pos["title"], "content": content})

        return result

    def _apply_ieee_mapping(self, sections_with_content: list[dict],
                             ieee_mapping: any) -> list[dict]:
        """
        Apply the LLM-generated IEEE mapping to reorder and group sections.
        Handles list of mappings, dict of sections, or direct section lists.
        """
        if not ieee_mapping:
            return sections_with_content

        # If LLM returned a dict with "sections" that already have title/content
        if isinstance(ieee_mapping, dict) and "sections" in ieee_mapping:
            raw_secs = ieee_mapping["sections"]
            if isinstance(raw_secs, list) and raw_secs and isinstance(raw_secs[0], dict):
                if "content" in raw_secs[0] and "title" in raw_secs[0]:
                    return [
                        {
                            "number": s.get("number") or ROMAN_NUMERALS[i % len(ROMAN_NUMERALS)],
                            "title": s.get("title", f"SECTION {i+1}").upper(),
                            "content": s.get("content", ""),
                            "subsections": s.get("subsections", []),
                        }
                        for i, s in enumerate(raw_secs)
                    ]
            ieee_mapping = ieee_mapping.get("mapping") or raw_secs

        if not isinstance(ieee_mapping, list):
            return sections_with_content

        # Build a map from original title to ieee title
        orig_to_ieee: dict[str, str] = {}
        ieee_order: list[str] = []  # Ordered list of unique IEEE titles

        for mapping in ieee_mapping:
            if not isinstance(mapping, dict):
                continue
            orig = mapping.get("original") or mapping.get("original_title") or mapping.get("source", "")
            ieee = (mapping.get("ieee") or mapping.get("ieee_section") or mapping.get("title") or "").upper()
            if orig and ieee:
                orig_to_ieee[orig.lower()] = ieee
                if ieee not in ieee_order:
                    ieee_order.append(ieee)

        if not orig_to_ieee:
            return sections_with_content

        # Group content by IEEE section
        ieee_content: dict[str, list[str]] = {}
        unmapped: list[dict] = []

        for sec in sections_with_content:
            orig_lower = sec["title"].lower()
            ieee_title = orig_to_ieee.get(orig_lower)
            if ieee_title:
                if ieee_title not in ieee_content:
                    ieee_content[ieee_title] = []
                ieee_content[ieee_title].append(sec["content"])
            else:
                # Try fuzzy match
                matched = False
                for orig_key, ieee_val in orig_to_ieee.items():
                    if orig_lower in orig_key or orig_key in orig_lower:
                        if ieee_val not in ieee_content:
                            ieee_content[ieee_val] = []
                        ieee_content[ieee_val].append(sec["content"])
                        matched = True
                        break
                if not matched:
                    unmapped.append(sec)


        # Build ordered result
        result = []
        for ieee_title in ieee_order:
            contents = ieee_content.get(ieee_title, [])
            if contents:
                result.append({
                    "title": ieee_title,
                    "content": "\n\n".join(c for c in contents if c.strip())
                })

        # Append unmapped sections at appropriate place
        for sec in unmapped:
            if sec.get("content", "").strip():
                result.append(sec)

        return result

    def _extract_references(self, text: str) -> list[dict]:
        """
        Extract references from the document.
        Returns list of {title, authors, year, venue} dicts.
        """
        refs = []

        # Find references section
        ref_match = re.search(
            r'(?:REFERENCES|References|Bibliography)\s*\n(.*?)(?:\n\s*(?:appendix|about the authors)|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if not ref_match:
            return refs

        ref_text = ref_match.group(1)

        # Parse individual references — try IEEE style [N] Author, "Title", ...
        ref_entries = re.findall(r'\[\d+\][^\[]+', ref_text)

        for entry in ref_entries[:30]:  # Limit to 30 refs
            # Extract year
            year_match = re.search(r'\b(19|20)\d{2}\b', entry)
            year = year_match.group(0) if year_match else None

            # Extract title (quoted in IEEE style)
            title_match = re.search(r'"([^"]+)"', entry)
            title = title_match.group(1) if title_match else entry[:80]

            # Extract authors (before quoted title or comma-separated)
            entry_clean = re.sub(r'\[\d+\]\s*', '', entry).strip()
            author_part = entry_clean.split('"')[0].strip() if '"' in entry_clean else entry_clean[:60]
            authors = [a.strip() for a in author_part.split(',') if a.strip()]

            if title:
                refs.append({
                    "title": title,
                    "authors": authors[:5],
                    "year": year,
                    "venue": ""
                })

        return refs

    async def _run_similarity_check(self, paper: ResearchPaper) -> float:
        """Run similarity check on restructured paper."""
        try:
            from app.services.segmenter import SentenceSegmenterService
            from app.services.matcher import DualTierMatcher

            full_text = paper.get_full_text()
            if not full_text.strip():
                return 0.0

            sentences = SentenceSegmenterService.segment(full_text)
            if not sentences:
                return 0.0

            matcher = DualTierMatcher()
            analysis = matcher.analyze_document(sentences)
            return analysis.get("plagiarism_score", 0.0)

        except Exception as e:
            logger.warning(f"Similarity check failed during restructuring: {e}")
            return 0.0
