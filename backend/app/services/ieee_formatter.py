"""
Academic Paper Formatter Service — formats ResearchPaper objects according to
18 official academic publisher guidelines (IEEE, Springer, Elsevier, ACM, Wiley,
Taylor & Francis, SAGE, MDPI, Frontiers, Nature, APA, Vancouver, MLA, Chicago,
AMA, ACS, AIP, APS).
"""
from __future__ import annotations

import html
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.schemas.research import ResearchPaper, PaperSection, Citation

logger = logging.getLogger(__name__)

ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]

FORMAT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "ieee": {
        "name": "IEEE Conference & Transactions",
        "columns": 2,
        "numbering_style": "roman",         # I. INTRODUCTION, III-A. Data Collection
        "title_case": "upper",
        "abstract_label": "Abstract—",
        "keywords_label": "Index Terms—",
        "references_heading": "REFERENCES",
        "citation_style": "bracket",
        "meta_header": "IEEE TRANSACTIONS ON COMPUTATIONAL INTELLIGENCE & RESEARCH • OFFICIAL CONFERENCE TEMPLATE",
    },
    "springer": {
        "name": "Springer Nature (LNCS / SN)",
        "columns": 1,
        "numbering_style": "arabic",        # 1 Introduction, 1.1 Data Collection
        "title_case": "title",
        "abstract_label": "Abstract.",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "SPRINGER NATURE • COMMUNICATIONS IN COMPUTER AND INFORMATION SCIENCE",
    },
    "elsevier": {
        "name": "Elsevier (ScienceDirect)",
        "columns": 2,
        "numbering_style": "decimal",       # 1. Introduction, 1.1. Data Collection
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "ELSEVIER SCIENCEDIRECT • PROCEDIA COMPUTER SCIENCE & ARTIFICIAL INTELLIGENCE",
    },
    "acm": {
        "name": "ACM Standard (SIGCONF)",
        "columns": 2,
        "numbering_style": "arabic_dot",    # 1. INTRODUCTION, 1.1 Data Collection
        "title_case": "upper",
        "abstract_label": "ABSTRACT",
        "keywords_label": "CCS CONCEPTS • KEYWORDS",
        "references_heading": "REFERENCES",
        "citation_style": "bracket",
        "meta_header": "ACM TRANSACTIONS / SIGCONF • ACM INTERNATIONAL CONFERENCE PROCEEDINGS SERIES",
    },
    "wiley": {
        "name": "Wiley Journal Publishing",
        "columns": 1,
        "numbering_style": "arabic",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "WILEY ONLINE LIBRARY • PEER REVIEWED JOURNAL MANUSCRIPT",
    },
    "taylor_francis": {
        "name": "Taylor & Francis",
        "columns": 1,
        "numbering_style": "arabic",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "TAYLOR & FRANCIS GROUP • SCHOLARLY RESEARCH MANUSCRIPT",
    },
    "sage": {
        "name": "SAGE Publishing",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "SAGE PUBLICATIONS • PEER-REVIEWED RESEARCH JOURNAL",
    },
    "mdpi": {
        "name": "MDPI Open Access",
        "columns": 2,
        "numbering_style": "arabic_dot",
        "title_case": "title",
        "abstract_label": "Abstract:",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "MDPI OPEN ACCESS JOURNALS • PEER-REVIEWED SCIENTIFIC ARTICLE",
    },
    "frontiers": {
        "name": "Frontiers in Science",
        "columns": 2,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "bracket",
        "meta_header": "FRONTIERS RESEARCH FOUNDATION • SCIENTIFIC MANUSCRIPT",
    },
    "nature": {
        "name": "Nature Portfolio",
        "columns": 2,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Summary",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "superscript",
        "meta_header": "NATURE RESEARCH • SCIENTIFIC REPORTS & PROTOCOLS",
    },
    "apa": {
        "name": "APA 7th Edition",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "author_date",
        "meta_header": "AMERICAN PSYCHOLOGICAL ASSOCIATION (APA 7TH ED.) • SCHOLARLY MANUSCRIPT",
    },
    "vancouver": {
        "name": "Vancouver Biomedical",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "number",
        "meta_header": "INTERNATIONAL COMMITTEE OF MEDICAL JOURNAL EDITORS (ICMJE) • VANCOUVER STYLE",
    },
    "mla": {
        "name": "MLA 9th Edition",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "Works Cited",
        "citation_style": "author_page",
        "meta_header": "MODERN LANGUAGE ASSOCIATION (MLA 9TH ED.) • RESEARCH ESSAY",
    },
    "chicago": {
        "name": "Chicago 17th Edition",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "Bibliography",
        "citation_style": "author_date",
        "meta_header": "THE CHICAGO MANUAL OF STYLE (17TH ED.) • SCHOLARLY PUBLICATION",
    },
    "ama": {
        "name": "AMA (American Medical Association)",
        "columns": 1,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "superscript",
        "meta_header": "AMERICAN MEDICAL ASSOCIATION (AMA MANUAL OF STYLE) • CLINICAL MANUSCRIPT",
    },
    "acs": {
        "name": "ACS (American Chemical Society)",
        "columns": 2,
        "numbering_style": "none",
        "title_case": "title",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "References",
        "citation_style": "superscript",
        "meta_header": "AMERICAN CHEMICAL SOCIETY (ACS PUBLICATIONS) • RESEARCH ARTICLE",
    },
    "aip": {
        "name": "AIP (American Institute of Physics)",
        "columns": 2,
        "numbering_style": "roman",
        "title_case": "upper",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "REFERENCES",
        "citation_style": "bracket",
        "meta_header": "AMERICAN INSTITUTE OF PHYSICS (AIP PUBLISHING) • PEER-REVIEWED PAPER",
    },
    "aps": {
        "name": "APS (American Physical Society - Physical Review)",
        "columns": 2,
        "numbering_style": "roman",
        "title_case": "upper",
        "abstract_label": "Abstract",
        "keywords_label": "Keywords:",
        "references_heading": "REFERENCES",
        "citation_style": "bracket",
        "meta_header": "PHYSICAL REVIEW JOURNALS • AMERICAN PHYSICAL SOCIETY (APS)",
    },
}


class IEEEFormatterService:
    """
    Multi-Format Academic Formatter Service.
    Applies formatting conventions for IEEE and 17 other academic publishers
    to ResearchPaper objects. Fully backward compatible with legacy IEEE calls.
    """

    @classmethod
    def get_config(cls, format_style: Optional[str] = "ieee") -> Dict[str, Any]:
        """Return configuration dictionary for a given academic format."""
        key = (format_style or "ieee").lower()
        return FORMAT_CONFIGS.get(key, FORMAT_CONFIGS["ieee"])

    @classmethod
    def format_paper(cls, paper: ResearchPaper, format_style: Optional[str] = None) -> ResearchPaper:
        """
        Apply publisher-specific formatting conventions to a paper in-place:
        - Section numbers (Roman, Arabic, Decimal, or None)
        - Section titles (UPPERCASE vs Title Case)
        - Subsection labels (A/B vs 1.1/1.2)
        - Citation references ordering
        Returns the modified paper.
        """
        target_fmt = (format_style or paper.format_style or "ieee").lower()
        paper.format_style = target_fmt
        cfg = cls.get_config(target_fmt)

        numbering_style = cfg.get("numbering_style", "roman")
        title_case = cfg.get("title_case", "upper")

        for i, section in enumerate(paper.sections):
            # Title case
            clean_title = section.title.strip()
            # Remove any leading existing number e.g. "I. ", "1. "
            import re
            clean_title = re.sub(r'^(?:[IVXLCDM]+\.|\d+\.|\d+)\s*', '', clean_title)

            if title_case == "upper":
                section.title = clean_title.upper()
            else:
                section.title = clean_title.title()

            # Section number
            if numbering_style == "roman":
                section.number = ROMAN_NUMERALS[i] if i < len(ROMAN_NUMERALS) else str(i + 1)
            elif numbering_style == "arabic":
                section.number = str(i + 1)
            elif numbering_style in ("arabic_dot", "decimal"):
                section.number = f"{i + 1}."
            else:
                # none / unnumbered (APA, MLA, Chicago, Nature, SAGE, Frontiers, ACS, AMA)
                section.number = ""

            # Subsections
            for j, sub in enumerate(section.subsections):
                sub_clean = re.sub(r'^(?:[A-Z]\.|\d+\.\d+\.?)\s*', '', sub.title.strip())
                if title_case == "upper":
                    sub.title = sub_clean.upper()
                else:
                    sub.title = sub_clean.title()

                if numbering_style == "roman":
                    sub.label = chr(ord('A') + j)
                elif numbering_style in ("arabic", "arabic_dot", "decimal"):
                    sub.label = f"{i + 1}.{j + 1}"
                else:
                    sub.label = ""

        return paper

    @classmethod
    def to_html_preview(cls, paper: ResearchPaper) -> str:
        """
        Generate an HTML representation of the paper for preview in the frontend.
        Respects 1-column vs 2-column layout, publisher header, and specific labels.
        """
        target_fmt = (paper.format_style or "ieee").lower()
        cfg = cls.get_config(target_fmt)
        parts = []

        # Journal / Publisher Meta Header Banner
        meta_banner = cfg.get("meta_header", "ACADEMIC RESEARCH PAPER")
        parts.append(f'<div class="paper-journal-meta">{html.escape(meta_banner)}</div>')

        # Title
        if paper.title:
            parts.append(f'<h1 class="paper-title-preview" id="paper-editable-title">{html.escape(paper.title)}</h1>')

        # Authors
        authors = paper.authors or ["1st Given Name Surname", "2nd Given Name Surname", "3rd Given Name Surname"]
        parts.append('<div class="paper-authors-grid">')
        default_affils = [
            {"dept": "Dept. of Computer Science & Eng.", "org": "Lemma AI Research Laboratory", "loc": "New York, USA", "email": "author1@lemma.ai"},
            {"dept": "Dept. of Electrical & Data Systems", "org": "Lemma AI Research Laboratory", "loc": "Boston, USA", "email": "author2@lemma.ai"},
            {"dept": "Dept. of Information Intelligence", "org": "Lemma AI Research Laboratory", "loc": "San Francisco, USA", "email": "author3@lemma.ai"}
        ]
        for idx in range(min(3, max(1, len(authors)))):
            a_name = authors[idx] if idx < len(authors) else f"Author {idx+1}"
            aff = default_affils[idx] if idx < len(default_affils) else default_affils[0]
            parts.append(
                f'<div class="paper-author-card">'
                f'<div class="author-name author-name-editable">{html.escape(a_name)}</div>'
                f'<div class="author-dept author-field-editable">{aff["dept"]}</div>'
                f'<div class="author-org author-field-editable">({aff["org"]})</div>'
                f'<div class="author-loc author-field-editable">{aff["loc"]}</div>'
                f'<div class="author-email author-field-editable">{aff["email"]}</div>'
                f'</div>'
            )
        parts.append('</div>')

        # Body Container: 2-column vs 1-column
        body_col_class = "paper-two-column-body" if cfg.get("columns", 2) == 2 else "paper-one-column-body"
        parts.append(f'<div class="{body_col_class}">')

        # Abstract
        abstract_text = (paper.abstract or '').strip()
        if not abstract_text:
            abstract_text = (
                f"This document presents a comprehensive theoretical and empirical investigation into {paper.topic or 'the designated domain'}. "
                f"By synthesizing contemporary methodologies and rigorous mathematical formulations, we establish an end-to-end framework "
                f"that addresses algorithmic bottlenecks and operational constraints across standardized evaluation environments."
            )
        abs_label = cfg.get("abstract_label", "Abstract—")
        parts.append('<div class="paper-abstract-preview" id="section-abstract">')
        parts.append(f'<span class="ieee-run-in">{html.escape(abs_label)} </span>')
        parts.append(f'<span class="abstract-content-editable">{html.escape(abstract_text)}</span>')
        parts.append('</div>')

        # Keywords
        kw_list = paper.keywords if (paper.keywords and isinstance(paper.keywords, list)) else []
        if not kw_list:
            topic_words = [w.capitalize() for w in (paper.topic or 'Research Investigation').split() if len(w) > 3][:5]
            kw_list = topic_words + ['Scientific Benchmarks', 'Empirical Evaluation', 'Algorithmic Optimization']
        kw_str = ", ".join(kw_list)
        kw_label = cfg.get("keywords_label", "Keywords:")
        parts.append(f'<div class="paper-keywords-preview"><span class="ieee-run-in">{html.escape(kw_label)} </span>{html.escape(kw_str)}</div>')

        # Sections
        for idx, section in enumerate(paper.sections):
            prefix = f"{section.number} " if section.number else ""
            if section.number and not section.number.endswith('.'):
                prefix = f"{section.number}. "

            parts.append(
                f'<div class="paper-section-preview" id="section-{section.number or idx}">'
                f'<h2 class="paper-section-heading-preview">'
                f'<span class="sec-num-label">{html.escape(prefix)}</span>'
                f'<span class="sec-title-editable">{html.escape(section.title)}</span>'
                f'</h2>'
            )
            if section.content:
                formatted_content = cls._format_inline_citations(
                    html.escape(section.content), cfg.get("citation_style", "bracket")
                )
                parts.append(f'<div class="paper-section-body-text">{formatted_content}</div>')

            # Subsections
            for sub in section.subsections:
                sub_prefix = f"{sub.label}. " if sub.label else ""
                parts.append(
                    f'<h3 class="paper-subsection-heading-preview">'
                    f'<span class="sub-label">{html.escape(sub_prefix)}</span>'
                    f'<span>{html.escape(sub.title)}</span>'
                    f'</h3>'
                )
                if sub.content:
                    formatted_sub = cls._format_inline_citations(
                        html.escape(sub.content), cfg.get("citation_style", "bracket")
                    )
                    parts.append(f'<div class="paper-section-body-text">{formatted_sub}</div>')

            parts.append('</div>')

        # References / Bibliography
        if paper.citations:
            ref_heading = cfg.get("references_heading", "REFERENCES")
            parts.append(f'<h2 class="paper-section-heading-preview">{html.escape(ref_heading)}</h2>')
            parts.append('<div class="paper-references-preview">')
            for citation in sorted(paper.citations, key=lambda c: c.number):
                ref_str = citation.formatted_reference_string(target_fmt)
                parts.append(f'<p class="paper-ref-preview" id="ref-{citation.number}">{html.escape(ref_str)}</p>')
            parts.append('</div>')

        # Close body
        parts.append('</div>')

        return "\n".join(parts)

    @staticmethod
    def _format_inline_citations(escaped_text: str, citation_style: str = "bracket") -> str:
        """Convert escaped [N] citation markers to styled HTML elements."""
        import re
        if citation_style == "superscript":
            return re.sub(
                r'\[(\d+)\]',
                r'<sup class="paper-citation"><a href="#ref-\1">\1</a></sup>',
                escaped_text
            )
        return re.sub(
            r'\[(\d+)\]',
            r'<sup class="paper-citation">[<a href="#ref-\1">\1</a>]</sup>',
            escaped_text
        )

    @classmethod
    def to_full_pdf_html(cls, paper: ResearchPaper) -> str:
        """
        Generate a full HTML document for PDF rendering via WeasyPrint fallback.
        Includes responsive CSS for 1-column vs 2-column layouts.
        """
        body_content = cls.to_html_preview(paper)
        cfg = cls.get_config(paper.format_style)
        is_two_col = cfg.get("columns", 2) == 2
        col_css = """
        .paper-two-column-body {
            column-count: 2;
            column-gap: 18pt;
            column-rule: 0.5pt solid #e2e8f0;
        }
        .paper-one-column-body {
            column-count: 1;
            max-width: 650pt;
            margin: 0 auto;
        }
        """

        sim_score_pct = int(round((paper.similarity_score or 0.0) * 100))
        sim_color = "#10b981" if sim_score_pct < 20 else "#f59e0b" if sim_score_pct < 40 else "#ef4444"
        current_time = datetime.now().strftime("%Y-%m-%d")
        source_count = len(paper.sources) if paper.sources else len(paper.citations)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(paper.title or 'Research Paper')}</title>
    <style>
        @page {{
            size: A4;
            margin: 20mm 15mm 20mm 15mm;
            @bottom-center {{
                content: counter(page);
                font-family: 'Times New Roman', serif;
                font-size: 9pt;
            }}
        }}

        body {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 9.5pt;
            line-height: 1.45;
            color: #000000;
            margin: 0;
            padding: 0;
        }}

        .paper-journal-meta {{
            text-align: center;
            font-size: 7.5pt;
            letter-spacing: 0.5pt;
            color: #64748b;
            border-bottom: 1px solid #cbd5e1;
            margin-bottom: 12pt;
            padding-bottom: 4pt;
            text-transform: uppercase;
        }}

        .paper-title-preview {{
            font-size: 16pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 8pt;
            font-family: 'Times New Roman', serif;
            line-height: 1.25;
        }}

        .paper-authors-grid {{
            display: flex;
            justify-content: center;
            gap: 20pt;
            text-align: center;
            margin-bottom: 14pt;
        }}

        .paper-author-card {{
            font-size: 8pt;
            line-height: 1.2;
        }}

        .author-name {{
            font-weight: bold;
            font-size: 9pt;
            margin-bottom: 2pt;
        }}

        {col_css}

        .paper-abstract-preview {{
            font-size: 8.5pt;
            text-align: justify;
            margin-bottom: 8pt;
        }}

        .ieee-run-in {{
            font-weight: bold;
            font-style: italic;
        }}

        .paper-keywords-preview {{
            font-size: 8.5pt;
            text-align: justify;
            margin-bottom: 10pt;
        }}

        .paper-section-heading-preview {{
            font-size: 9.5pt;
            font-weight: bold;
            margin-top: 10pt;
            margin-bottom: 4pt;
            font-family: 'Times New Roman', serif;
        }}

        .paper-subsection-heading-preview {{
            font-size: 9pt;
            font-weight: bold;
            font-style: italic;
            margin-top: 6pt;
            margin-bottom: 2pt;
        }}

        .paper-section-body-text {{
            text-align: justify;
            text-indent: 14pt;
            margin-bottom: 6pt;
            font-size: 9.5pt;
        }}

        .paper-references-preview {{
            font-size: 8pt;
            margin-top: 10pt;
        }}

        .paper-ref-preview {{
            margin-bottom: 3pt;
            text-indent: -14pt;
            padding-left: 14pt;
        }}

        .paper-citation {{
            font-size: 7.5pt;
            vertical-align: super;
        }}

        .paper-similarity-footer {{
            margin-top: 15mm;
            padding-top: 4mm;
            border-top: 1pt solid #cbd5e1;
            font-size: 7.5pt;
            color: #64748b;
        }}
    </style>
</head>
<body>
    {body_content}

    <div class="paper-similarity-footer">
        <strong>Publishing &amp; Similarity Report:</strong> Format: {html.escape(cfg.get('name', 'Academic Paper'))} |
        Overall similarity score: {sim_score_pct}% | Sources referenced: {source_count} |
        Generated by Lemma AI Research Laboratory.
    </div>
</body>
</html>"""


# Alias for intuitive discovery
PaperFormatterService = IEEEFormatterService
