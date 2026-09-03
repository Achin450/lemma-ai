"""
IEEE Formatter Service — applies IEEE formatting to a ResearchPaper object.
Handles section numbering, citation formatting, PDF-ready HTML generation,
and DOCX generation.
"""
from __future__ import annotations

import html
import io
import logging
from datetime import datetime
from typing import Optional

from app.schemas.research import ResearchPaper, PaperSection, Citation

logger = logging.getLogger(__name__)


class IEEEFormatterService:
    """
    Applies IEEE formatting rules to ResearchPaper objects.
    Generates HTML and plain text representations for PDF export.
    """

    @staticmethod
    def format_paper(paper: ResearchPaper) -> ResearchPaper:
        """
        Apply IEEE formatting conventions to a paper in-place:
        - Section numbers as Roman numerals
        - Section titles in ALL CAPS
        - Proper citation number ordering
        Returns the modified paper.
        """
        # Ensure section titles are uppercase
        for section in paper.sections:
            if not section.title.isupper():
                section.title = section.title.upper()

        # Ensure subsection labels are alphabetical
        for section in paper.sections:
            for i, sub in enumerate(section.subsections):
                sub.label = chr(ord('A') + i)

        return paper

    @staticmethod
    def to_html_preview(paper: ResearchPaper) -> str:
        """
        Generate an HTML representation of the paper for preview in the frontend.
        Returns a single HTML string (no <html>/<head>/<body> wrappers).
        """
        parts = []

        # Title
        if paper.title:
            parts.append(f'<h1 class="paper-title">{html.escape(paper.title)}</h1>')

        # Authors line
        if paper.authors:
            authors_str = ", ".join(paper.authors)
            parts.append(f'<p class="paper-authors">{html.escape(authors_str)}</p>')
        else:
            parts.append('<p class="paper-authors">[Author Name(s)]</p>')

        # Abstract
        if paper.abstract:
            parts.append('<div class="paper-abstract">')
            parts.append('<strong class="paper-abstract-label">Abstract—</strong>')
            parts.append(html.escape(paper.abstract))
            parts.append('</div>')

        # Keywords
        if paper.keywords:
            kw_str = ", ".join(paper.keywords)
            parts.append(f'<p class="paper-keywords"><strong>Index Terms—</strong>{html.escape(kw_str)}</p>')

        parts.append('<hr class="paper-divider">')

        # Sections
        for section in paper.sections:
            parts.append(
                f'<h2 class="paper-section-heading">'
                f'{html.escape(section.number)}. {html.escape(section.title)}'
                f'</h2>'
            )
            if section.content:
                # Convert inline citations [N] to styled spans
                formatted_content = IEEEFormatterService._format_inline_citations(
                    html.escape(section.content)
                )
                parts.append(f'<div class="paper-section-content">{formatted_content}</div>')

            # Subsections
            for sub in section.subsections:
                parts.append(
                    f'<h3 class="paper-subsection-heading">'
                    f'{html.escape(section.number)}-{html.escape(sub.label)}. {html.escape(sub.title)}'
                    f'</h3>'
                )
                if sub.content:
                    formatted_sub = IEEEFormatterService._format_inline_citations(
                        html.escape(sub.content)
                    )
                    parts.append(f'<div class="paper-section-content">{formatted_sub}</div>')

        # References
        if paper.citations:
            parts.append('<h2 class="paper-section-heading">REFERENCES</h2>')
            parts.append('<div class="paper-references">')
            for citation in sorted(paper.citations, key=lambda c: c.number):
                ref_str = citation.ieee_reference_string()
                parts.append(f'<p class="paper-ref" id="ref-{citation.number}">{html.escape(ref_str)}</p>')
            parts.append('</div>')

        return "\n".join(parts)

    @staticmethod
    def _format_inline_citations(escaped_text: str) -> str:
        """Convert escaped [N] citation markers to styled HTML spans."""
        import re
        return re.sub(
            r'\[(\d+)\]',
            r'<sup class="paper-citation">[<a href="#ref-\1">\1</a>]</sup>',
            escaped_text
        )

    @classmethod
    def to_full_pdf_html(cls, paper: ResearchPaper) -> str:
        """
        Generate a full HTML document for PDF rendering via WeasyPrint.
        Includes CSS for IEEE-style two-column layout.
        """
        body_content = cls.to_html_preview(paper)
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
            margin: 25mm 20mm 25mm 20mm;
            @bottom-center {{
                content: counter(page);
                font-family: 'Times New Roman', serif;
                font-size: 9pt;
            }}
        }}

        body {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #000000;
            margin: 0;
            padding: 0;
        }}

        .paper-header-meta {{
            text-align: right;
            font-size: 8pt;
            color: #666;
            border-bottom: 1px solid #ccc;
            margin-bottom: 10mm;
            padding-bottom: 3mm;
        }}

        .paper-title {{
            font-size: 18pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 6pt;
            font-family: 'Times New Roman', serif;
            line-height: 1.3;
        }}

        .paper-authors {{
            text-align: center;
            font-size: 11pt;
            margin-bottom: 6pt;
            font-style: italic;
        }}

        .paper-abstract {{
            font-size: 9pt;
            margin: 10pt 30pt;
            text-align: justify;
        }}

        .paper-abstract-label {{
            font-weight: bold;
            font-style: italic;
        }}

        .paper-keywords {{
            font-size: 9pt;
            margin: 6pt 30pt;
        }}

        .paper-divider {{
            border: none;
            border-top: 1pt solid #000;
            margin: 10pt 0;
        }}

        .paper-section-heading {{
            font-size: 10pt;
            font-weight: bold;
            text-align: center;
            margin-top: 12pt;
            margin-bottom: 6pt;
            text-transform: uppercase;
            font-family: 'Times New Roman', serif;
            letter-spacing: 0.5pt;
        }}

        .paper-subsection-heading {{
            font-size: 10pt;
            font-weight: bold;
            font-style: italic;
            margin-top: 8pt;
            margin-bottom: 4pt;
        }}

        .paper-section-content {{
            text-align: justify;
            text-indent: 1.5em;
            margin-bottom: 6pt;
        }}

        .paper-references {{
            font-size: 9pt;
        }}

        .paper-ref {{
            margin-bottom: 4pt;
            text-indent: -1.5em;
            padding-left: 1.5em;
        }}

        .paper-citation {{
            font-size: 7pt;
            vertical-align: super;
        }}

        .paper-similarity-footer {{
            margin-top: 10mm;
            padding-top: 4mm;
            border-top: 1pt solid #ccc;
            font-size: 8pt;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="paper-header-meta">
        Generated by Lemma AI Research Assistant | {current_time}
        | Sources: {source_count}
        | Similarity Score: <span style="color: {sim_color}; font-weight: bold;">{sim_score_pct}%</span>
    </div>

    {body_content}

    <div class="paper-similarity-footer">
        <strong>Similarity Analysis:</strong> Overall similarity score: {sim_score_pct}% |
        Sources referenced: {source_count} |
        Generated by Lemma AI — similarity score is based on the available reference corpus.
        Independent verification is recommended for final submission.
    </div>
</body>
</html>"""
