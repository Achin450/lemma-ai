import io
import html
import datetime
class PDFGeneratorService:
    """
    Generates beautiful, production-grade PDF plagiarism analysis reports using WeasyPrint.
    Uses HTML templates and CSS Paged Media rules.
    """

    @staticmethod
    def _get_highlighted_html(text: str, sentences: list[dict], matches: list[dict]) -> str:
        """
        Reconstructs the original document text with word-level <mark> highlights
        based on plagiarism coordinate mappings.
        """
        # Map sentence start_char to its match for quick lookup
        matches_map = {m["query_sentence"]["start_char"]: m for m in matches}
        
        html_parts = []
        last_offset = 0
        
        for s in sentences:
            start = s["start_char"]
            end = s["end_char"]
            
            # Append any raw text between sentences (spaces, newlines, etc.)
            if start > last_offset:
                raw_between = text[last_offset:start]
                # Replace newlines with <br> to preserve line breaks
                html_parts.append(html.escape(raw_between).replace("\n", "<br>"))
                
            sent_text = s["text"]
            match = matches_map.get(start)
            
            if match:
                highlights = match.get("highlights", [])
                if highlights:
                    # Sort highlights by relative start offset in the sentence
                    sorted_hls = []
                    for hl in highlights:
                        rel_start = hl["start_char"] - start
                        rel_end = hl["end_char"] - start
                        # Make sure boundaries are within bounds
                        if 0 <= rel_start < rel_end <= len(sent_text):
                            sorted_hls.append((rel_start, rel_end, hl["text"]))
                            
                    sorted_hls.sort(key=lambda x: x[0])
                    
                    # Merge overlapping or touching highlights relative to sentence
                    merged_hls = []
                    if sorted_hls:
                        merged_hls.append(sorted_hls[0])
                        for curr in sorted_hls[1:]:
                            prev = merged_hls[-1]
                            if curr[0] <= prev[1]:
                                merged_hls[-1] = (prev[0], max(prev[1], curr[1]), sent_text[prev[0]:max(prev[1], curr[1])])
                            else:
                                merged_hls.append(curr)
                                
                    sent_html = []
                    last_sent_idx = 0
                    
                    for rel_start, rel_end, hl_text in merged_hls:
                        if rel_start > last_sent_idx:
                            sent_html.append(html.escape(sent_text[last_sent_idx:rel_start]))
                        
                        if match["match_type"] == "lexical":
                            mark_class = "mark-lexical"
                        elif match["match_type"] == "hybrid":
                            mark_class = "mark-hybrid"
                        else:
                            mark_class = "mark-semantic"
                        sent_html.append(f'<mark class="{mark_class}">{html.escape(sent_text[rel_start:rel_end])}</mark>')
                        last_sent_idx = rel_end
                        
                    if last_sent_idx < len(sent_text):
                        sent_html.append(html.escape(sent_text[last_sent_idx:]))
                    
                    sentence_html_content = "".join(sent_html)
                else:
                    if match["match_type"] == "lexical":
                        mark_class = "mark-lexical"
                    elif match["match_type"] == "hybrid":
                        mark_class = "mark-hybrid"
                    else:
                        mark_class = "mark-semantic"
                    sentence_html_content = f'<mark class="{mark_class}">{html.escape(sent_text)}</mark>'
            else:
                sentence_html_content = html.escape(sent_text)
                
            html_parts.append(sentence_html_content)
            last_offset = end
            
        # Append remaining trailing text
        if last_offset < len(text):
            raw_tail = text[last_offset:]
            html_parts.append(html.escape(raw_tail).replace("\n", "<br>"))
            
        return "".join(html_parts)

    @classmethod
    def generate_report(cls, data: dict) -> bytes:
        """
        Builds the HTML report structure and compiles it to PDF.
        """
        filename = data.get("filename", "unknown_document.txt")
        text = data.get("text", "")
        char_count = data.get("char_count", 0)
        sentence_count = data.get("sentence_count", 0)
        sentences = data.get("sentences", [])
        
        analysis = data.get("analysis", {}) or {}
        plag_score_float = analysis.get("plagiarism_score", 0.0)
        plag_score_pct = int(round(plag_score_float * 100))
        total_sents = analysis.get("total_sentences", 0)
        plag_sents_count = analysis.get("plagiarized_sentences_count", 0)
        lexical_count = analysis.get("lexical_matches_count", 0)
        semantic_count = analysis.get("semantic_matches_count", 0)
        hybrid_count = analysis.get("hybrid_matches_count", 0)
        matches = analysis.get("matches", [])
        
        # Calculate percentages
        lexical_pct = int(round((lexical_count / total_sents) * 100)) if total_sents > 0 else 0
        semantic_pct = int(round((semantic_count / total_sents) * 100)) if total_sents > 0 else 0
        hybrid_pct = int(round((hybrid_count / total_sents) * 100)) if total_sents > 0 else 0
        original_pct = max(0, 100 - lexical_pct - semantic_pct - hybrid_pct)
        
        # AI Detection vars
        ai = data.get("ai_detection", {}) or {}
        ai_score = int(round(ai.get("ai_score", 0.0) * 100))
        ai_confidence = ai.get("confidence", "Unknown")
        ai_perplexity = ai.get("perplexity_score", 0.0)
        ai_burstiness = ai.get("burstiness_score", 0.0)
        ai_flagged_sents = ai.get("flagged_sentence_count", 0)
        ai_fingerprints = ai.get("fingerprint_matches", [])

        # Citation Analysis vars
        cit = data.get("citation_analysis", {}) or {}
        cit_score = int(round(cit.get("citation_integrity_score", 1.0) * 100))
        cit_in_text = cit.get("total_in_text_citations", 0)
        cit_bib = cit.get("total_bibliography_entries", 0)
        cit_unsupported = len(cit.get("unsupported_citations", []))
        cit_padded = len(cit.get("padded_citations", []))
        cit_uncited = len(cit.get("uncited_paraphrases", []))
        cit_summary = cit.get("summary", "No citation analysis available.")

        # Format current timestamp
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Group top reference sources
        sources_summary = {}
        for m in matches:
            ref = m.get("matched_sentence", {})
            doc_id = ref.get("doc_id") or ref.get("document_id") or "unknown"
            doc_title = ref.get("doc_title") or ref.get("title") or "Unknown Reference"
            doc_author = ref.get("doc_author") or ref.get("author") or "N/A"
            doc_source = ref.get("doc_source") or ref.get("source") or "N/A"
            score = m.get("score", 0.0)
            m_type = m.get("match_type", "lexical")
            
            if doc_id not in sources_summary:
                sources_summary[doc_id] = {
                    "title": doc_title,
                    "author": doc_author,
                    "source": doc_source,
                    "count": 0,
                    "max_score": 0.0,
                    "types": set()
                }
            sources_summary[doc_id]["count"] += 1
            sources_summary[doc_id]["max_score"] = max(sources_summary[doc_id]["max_score"], score)
            sources_summary[doc_id]["types"].add(m_type)
            
        sorted_sources = sorted(
            sources_summary.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        # Build the sources table HTML
        sources_table_rows = ""
        if sorted_sources:
            for idx, src in enumerate(sorted_sources, 1):
                types_str = " / ".join(list(src["types"])).upper()
                max_score_pct = int(round(src["max_score"] * 100))
                sources_table_rows += f"""
                <tr>
                    <td>{idx}</td>
                    <td>
                        <strong>{html.escape(src["title"])}</strong><br>
                        <span style="font-size: 8pt; color: #64748b;">{html.escape(src["author"])} — {html.escape(src["source"])}</span>
                    </td>
                    <td>{src["count"]}</td>
                    <td><span class="badge badge-{list(src["types"])[0]}">{types_str}</span></td>
                    <td><strong>{max_score_pct}%</strong></td>
                </tr>
                """
        else:
            sources_table_rows = """
            <tr>
                <td colspan="5" style="text-align: center; color: #64748b; padding: 20px;">
                    No plagiarism sources detected. Document is 100% original.
                </td>
            </tr>
            """
            
        # Reconstruct highlighted text
        highlighted_content = cls._get_highlighted_html(text, sentences, matches)
        
        # Build detailed matched segments comparison
        detailed_comparisons = ""
        if matches:
            for idx, m in enumerate(matches, 1):
                q_sent = m.get("query_sentence", {}).get("text", "")
                ms = m.get("matched_sentence", {})
                r_sent = ms.get("text", "")
                ref_title = ms.get("doc_title") or ms.get("title") or "Reference Source"
                ref_citation = f"{ms.get('doc_author') or ms.get('author') or 'N/A'} — {ms.get('doc_source') or ms.get('source') or 'N/A'}"
                score_pct = int(round(m["score"] * 100))
                m_type = m["match_type"]
                type_label = "Lexical Match" if m_type == "lexical" else ("Hybrid Match" if m_type == "hybrid" else "Semantic Match")
                badge_class = "badge-lexical" if m_type == "lexical" else ("badge-hybrid" if m_type == "hybrid" else "badge-semantic")
                
                detailed_comparisons += f"""
                <div class="match-item">
                    <div class="match-item-header">
                        <span class="match-item-title">Segment #{idx}</span>
                        <div>
                            <span class="badge {badge_class}">{type_label}</span>
                            <span class="badge {badge_class}">{score_pct}% Similarity</span>
                        </div>
                    </div>
                    <div class="match-item-body">
                        <div style="font-size: 8.5pt; color: #64748b; margin-bottom: 8px;">
                            <strong>Reference Source:</strong> {html.escape(ref_title)} ({html.escape(ref_citation)})
                        </div>
                        <div class="comparison-grid">
                            <div class="comparison-column">
                                <div class="comparison-label">Analyzed Text</div>
                                <blockquote class="comparison-text">{html.escape(q_sent)}</blockquote>
                            </div>
                            <div class="comparison-column">
                                <div class="comparison-label">Source Text</div>
                                <blockquote class="comparison-text">{html.escape(r_sent)}</blockquote>
                            </div>
                        </div>
                    </div>
                </div>
                """
        else:
            detailed_comparisons = """
            <div style="text-align: center; color: #64748b; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 30px;">
                No matches to break down.
            </div>
            """
            
        # Overall HTML Template
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Lemma Plagiarism Analysis Report</title>
    <style>
        @page {{
            size: A4;
            margin: 20mm 15mm 20mm 15mm;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-family: 'Outfit', 'Inter', 'Helvetica Neue', sans-serif;
                font-size: 8pt;
                color: #64748b;
            }}
            @bottom-left {{
                content: "Lemma Academic Integrity Platform";
                font-family: 'Outfit', 'Inter', 'Helvetica Neue', sans-serif;
                font-size: 8pt;
                color: #64748b;
            }}
        }}
        
        body {{
            font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
            color: #1e293b;
            line-height: 1.5;
            margin: 0;
            padding: 0;
        }}

        h1, h2, h3, h4 {{
            font-family: 'Outfit', 'Helvetica Neue', Arial, sans-serif;
            color: #0f172a;
            margin-top: 0;
            font-weight: 700;
        }}

        .header {{
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}

        .header-title-container {{
            margin-bottom: 5px;
        }}

        .header-title {{
            font-size: 22pt;
            font-weight: 800;
            color: #0f172a;
            margin: 0;
            letter-spacing: -0.5px;
        }}

        .header-subtitle {{
            font-size: 8.5pt;
            color: #64748b;
            margin: 5px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }}

        .meta-table {{
            width: 100%;
            margin-top: 15px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            border-collapse: separate;
            border-spacing: 15px 8px;
        }}

        .meta-label {{
            font-weight: 600;
            color: #475569;
            font-size: 9pt;
            width: 30%;
        }}

        .meta-value {{
            color: #0f172a;
            font-size: 9pt;
        }}

        .section {{
            margin-bottom: 30px;
        }}

        .section-title {{
            font-size: 13pt;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
            margin-bottom: 12px;
            font-weight: 700;
            color: #0f172a;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Metrics layout */
        .metrics-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 10px 0;
            margin-bottom: 20px;
        }}

        .metric-card {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            text-align: center;
            background-color: #ffffff;
            width: 20%;
        }}

        .metric-card.primary {{
            background-color: #0f172a;
            color: #ffffff;
            border-color: #0f172a;
        }}

        .metric-value {{
            font-size: 24pt;
            font-weight: 800;
            margin: 5px 0;
            font-family: 'Outfit', 'Helvetica Neue', Arial, sans-serif;
        }}

        .metric-label {{
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #64748b;
            font-weight: 600;
        }}

        .metric-card.primary .metric-label {{
            color: #94a3b8;
        }}

        /* Content highlighting */
        .content-box {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 15px;
            background-color: #ffffff;
            font-size: 10pt;
            text-align: justify;
        }}

        .mark-lexical {{
            background-color: #fee2e2;
            color: #991b1b;
            border-bottom: 1px solid #fca5a5;
        }}

        .mark-semantic {{
            background-color: #f3e8ff;
            color: #6b21a8;
            border-bottom: 1px solid #d8b4fe;
        }}

        .mark-hybrid {{
            background-color: #fef3c7;
            color: #92400e;
            border-bottom: 1px solid #fde68a;
        }}

        /* Tables */
        table.sources-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}

        table.sources-table th, table.sources-table td {{
            border: 1px solid #e2e8f0;
            padding: 8px 10px;
            text-align: left;
            font-size: 9pt;
        }}

        table.sources-table th {{
            background-color: #f1f5f9;
            font-weight: 700;
            color: #334155;
        }}

        table.sources-table tr:nth-child(even) {{
            background-color: #f8fafc;
        }}

        .badge {{
            display: inline-block;
            padding: 2px 6px;
            font-size: 7.5pt;
            font-weight: 600;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .badge-lexical {{
            background-color: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }}

        .badge-semantic {{
            background-color: #f3e8ff;
            color: #6b21a8;
            border: 1px solid #d8b4fe;
        }}

        .badge-hybrid {{
            background-color: #fef3c7;
            color: #92400e;
            border: 1px solid #fde68a;
        }}

        /* Detailed Comparisons */
        .match-item {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 12px;
            background-color: #ffffff;
            page-break-inside: avoid;
        }}

        .match-item-header {{
            background-color: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .match-item-title {{
            font-size: 9pt;
            font-weight: 700;
            color: #334155;
            margin: 0;
        }}

        .match-item-body {{
            padding: 12px;
        }}

        .comparison-grid {{
            display: table;
            width: 100%;
            table-layout: fixed;
            margin-top: 5px;
        }}

        .comparison-column {{
            display: table-cell;
            width: 50%;
            vertical-align: top;
            padding-right: 10px;
        }}

        .comparison-column:last-child {{
            padding-right: 0;
            padding-left: 10px;
        }}

        .comparison-label {{
            font-weight: 600;
            color: #64748b;
            margin-bottom: 4px;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .comparison-text {{
            background-color: #f8fafc;
            border: 1px solid #f1f5f9;
            border-radius: 4px;
            padding: 8px;
            margin: 0;
            font-style: italic;
            font-size: 8.5pt;
            color: #334155;
        }}
        
        .page-break {{
            page-break-before: always;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title-container">
            <h1 class="header-title">Academic Integrity & Plagiarism Analysis</h1>
            <div class="header-subtitle">Lemma Plagiarism Detection Engine</div>
        </div>
        <table class="meta-table">
            <tr>
                <td class="meta-label">Analyzed Document:</td>
                <td class="meta-value">{html.escape(filename)}</td>
                <td class="meta-label">Date Generated:</td>
                <td class="meta-value">{current_time}</td>
            </tr>
            <tr>
                <td class="meta-label">Total Characters:</td>
                <td class="meta-value">{char_count:,}</td>
                <td class="meta-label">Total Sentences:</td>
                <td class="meta-value">{sentence_count:,}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <div class="section-title">Integrity Summary</div>
        <table class="metrics-table">
            <tr>
                <td class="metric-card primary">
                    <div class="metric-label">Plagiarism Score</div>
                    <div class="metric-value">{plag_score_pct}%</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Lexical Matches</div>
                    <div class="metric-value" style="color: #ef4444;">{lexical_pct}%</div>
                    <div style="font-size: 7.5pt; color: #64748b;">{lexical_count} sentence(s)</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Hybrid Matches</div>
                    <div class="metric-value" style="color: #f59e0b;">{hybrid_pct}%</div>
                    <div style="font-size: 7.5pt; color: #64748b;">{hybrid_count} sentence(s)</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Semantic Matches</div>
                    <div class="metric-value" style="color: #8b5cf6;">{semantic_pct}%</div>
                    <div style="font-size: 7.5pt; color: #64748b;">{semantic_count} sentence(s)</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Original Content</div>
                    <div class="metric-value" style="color: #10b981;">{original_pct}%</div>
                    <div style="font-size: 7.5pt; color: #64748b;">{total_sents - plag_sents_count} sentence(s)</div>
                </td>
            </tr>
        </table>
    </div>

    <div class="section">
        <div class="section-title">Top Reference Sources Matched</div>
        <table class="sources-table">
            <thead>
                <tr>
                    <th style="width: 5%;">#</th>
                    <th style="width: 55%;">Source Document Details</th>
                    <th style="width: 12%;">Matches</th>
                    <th style="width: 16%;">Match Type</th>
                    <th style="width: 12%;">Max Sim</th>
                </tr>
            </thead>
            <tbody>
                {sources_table_rows}
            </tbody>
        </table>
    </div>

    <div class="section">
        <div class="section-title">AI Content Detection</div>
        <table class="metrics-table">
            <tr>
                <td class="metric-card primary">
                    <div class="metric-label">AI Score</div>
                    <div class="metric-value" style="color: {'#ef4444' if ai_score >= 65 else '#f59e0b' if ai_score >= 40 else '#10b981'};">{ai_score}%</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Confidence</div>
                    <div class="metric-value" style="font-size: 14pt;">{ai_confidence}</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Perplexity</div>
                    <div class="metric-value">{ai_perplexity}</div>
                    <div style="font-size: 7.5pt; color: #64748b;">(Lower = more uniform)</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Burstiness</div>
                    <div class="metric-value">{ai_burstiness}</div>
                    <div style="font-size: 7.5pt; color: #64748b;">(0 = varied, 1 = uniform)</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Flagged Sentences</div>
                    <div class="metric-value">{ai_flagged_sents}</div>
                    <div style="font-size: 7.5pt; color: #64748b;">out of {total_sents}</div>
                </td>
            </tr>
        </table>
        {f'<div style="font-size: 9pt; color: #64748b; margin-top: 5px;"><strong>Detected Patterns:</strong> {", ".join(ai_fingerprints)}</div>' if ai_fingerprints else ''}
    </div>

    <div class="section">
        <div class="section-title">Citation Graph Analysis</div>
        <table class="metrics-table">
            <tr>
                <td class="metric-card primary">
                    <div class="metric-label">Integrity Score</div>
                    <div class="metric-value" style="color: {'#10b981' if cit_score >= 90 else '#f59e0b' if cit_score >= 70 else '#ef4444'};">{cit_score}%</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">In-Text Citations</div>
                    <div class="metric-value">{cit_in_text}</div>
                </td>
                <td class="metric-card">
                    <div class="metric-label">Bibliography Entries</div>
                    <div class="metric-value">{cit_bib}</div>
                </td>
                <td class="metric-card" style="border-color: {'#ef4444' if cit_unsupported else '#e2e8f0'};">
                    <div class="metric-label">Unsupported Claims</div>
                    <div class="metric-value">{cit_unsupported}</div>
                </td>
                <td class="metric-card" style="border-color: {'#f59e0b' if (cit_padded or cit_uncited) else '#e2e8f0'};">
                    <div class="metric-label">Other Issues</div>
                    <div class="metric-value">{cit_padded + cit_uncited}</div>
                    <div style="font-size: 7.5pt; color: #64748b;">Padding/Uncited</div>
                </td>
            </tr>
        </table>
        <div style="font-size: 9pt; color: #334155; margin-top: 5px; font-style: italic;">{cit_summary}</div>
    </div>

    <div class="page-break"></div>

    <div class="section">
        <div class="section-title">Document Content Analysis</div>
        <div class="content-box">
            {highlighted_content}
        </div>
    </div>

    <div class="page-break"></div>

    <div class="section">
        <div class="section-title">Segment-by-Segment Matching Breakdown</div>
        {detailed_comparisons}
    </div>
</body>
</html>
"""
        # Try WeasyPrint first if system libraries are present
        try:
            from weasyprint import HTML
            pdf_bytes = io.BytesIO()
            HTML(string=html_content).write_pdf(target=pdf_bytes)
            return pdf_bytes.getvalue()
        except Exception:
            # Fallback to robust pure-python ReportLab generator (ideal for Windows)
            return cls._generate_report_reportlab(data)

    @classmethod
    def _generate_report_reportlab(cls, data: dict) -> bytes:
        """
        Pure-Python ReportLab generator for official Lemma Academic Integrity & Plagiarism PDF reports.
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        story = []

        # Color palette
        PRIMARY = colors.HexColor('#0f172a')
        ACCENT_PURPLE = colors.HexColor('#6366f1')
        TEXT_DARK = colors.HexColor('#1e293b')
        TEXT_MUTED = colors.HexColor('#64748b')
        BG_LIGHT = colors.HexColor('#f8fafc')
        BORDER_LIGHT = colors.HexColor('#e2e8f0')
        COLOR_LEXICAL = colors.HexColor('#ef4444')
        COLOR_HYBRID = colors.HexColor('#f59e0b')
        COLOR_SEMANTIC = colors.HexColor('#8b5cf6')
        COLOR_ORIGINAL = colors.HexColor('#10b981')

        # Typography styles
        title_style = ParagraphStyle(
            'RepTitle', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=PRIMARY
        )
        subtitle_style = ParagraphStyle(
            'RepSub', parent=styles['Normal'],
            fontName='Helvetica', fontSize=8.5, leading=11, textColor=TEXT_MUTED
        )
        section_h1 = ParagraphStyle(
            'SecH1', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=PRIMARY,
            spaceBefore=12, spaceAfter=6
        )
        body_style = ParagraphStyle(
            'RepBody', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, leading=13.5, textColor=TEXT_DARK
        )
        table_cell_style = ParagraphStyle(
            'CellText', parent=styles['Normal'],
            fontName='Helvetica', fontSize=8.5, leading=11, textColor=TEXT_DARK
        )
        table_cell_bold = ParagraphStyle(
            'CellBold', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=PRIMARY
        )
        card_num_style = ParagraphStyle(
            'CardNum', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=22, leading=26, spaceAfter=3
        )
        card_title_style = ParagraphStyle(
            'CardTitle', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=PRIMARY, spaceAfter=2
        )
        card_sub_style = ParagraphStyle(
            'CardSub', parent=styles['Normal'],
            fontName='Helvetica', fontSize=8, leading=11, textColor=TEXT_MUTED
        )

        filename = data.get("filename", "document.txt")
        char_count = data.get("char_count", 0)
        sentence_count = data.get("sentence_count", 0)
        sentences = data.get("sentences", [])
        
        analysis = data.get("analysis", {}) or {}
        plag_score_float = analysis.get("plagiarism_score", 0.0) or 0.0
        plag_score_pct = int(round(plag_score_float * 100))
        total_sents = analysis.get("total_sentences", len(sentences)) or len(sentences)
        lexical_count = analysis.get("lexical_matches_count", 0)
        semantic_count = analysis.get("semantic_matches_count", 0)
        hybrid_count = analysis.get("hybrid_matches_count", 0)
        matches = analysis.get("matches", [])

        lexical_pct = int(round((lexical_count / total_sents) * 100)) if total_sents > 0 else 0
        semantic_pct = int(round((semantic_count / total_sents) * 100)) if total_sents > 0 else 0
        hybrid_pct = int(round((hybrid_count / total_sents) * 100)) if total_sents > 0 else 0
        original_pct = max(0, 100 - lexical_pct - semantic_pct - hybrid_pct)

        ai = data.get("ai_detection", {}) or {}
        ai_score = int(round(ai.get("ai_score", 0.0) * 100))
        ai_confidence = ai.get("confidence", "High")

        cit = data.get("citation_analysis", {}) or {}
        cit_score = int(round(cit.get("citation_integrity_score", 1.0) * 100))

        current_time = datetime.datetime.now().strftime("%B %d, %Y - %H:%M:%S")

        # 1. Header Block
        header_data = [
            [
                Paragraph("<b>LEMMA AI</b> &bull; Academic Integrity & Plagiarism Analysis", title_style),
                Paragraph(f"<b>Report Generated:</b><br/>{current_time}", subtitle_style)
            ],
            [
                Paragraph(f"<b>Document:</b> {html.escape(filename)} &nbsp;|&nbsp; <b>Chars:</b> {char_count:,} &nbsp;|&nbsp; <b>Sentences:</b> {sentence_count}", subtitle_style),
                Paragraph("<b>Engine:</b> Dual-Tier Lexical + pgvector Semantic", subtitle_style)
            ]
        ]
        t_header = Table(header_data, colWidths=[380, 160])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(t_header)
        story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=6, spaceAfter=14))

        # 2. Key Metrics Cards
        score_color = COLOR_ORIGINAL if plag_score_pct < 15 else (COLOR_HYBRID if plag_score_pct < 30 else COLOR_LEXICAL)
        
        c1_content = [
            Paragraph(f"<font color='{score_color.hexval()}'><b>{plag_score_pct}%</b></font>", card_num_style),
            Paragraph("Overall Similarity", card_title_style),
            Paragraph(f"{len(matches)} matched segments", card_sub_style)
        ]
        c2_content = [
            Paragraph(f"<font color='#6366f1'><b>{ai_score}%</b></font>", card_num_style),
            Paragraph("AI Probability", card_title_style),
            Paragraph(f"Confidence: {ai_confidence}", card_sub_style)
        ]
        c3_content = [
            Paragraph(f"<font color='#10b981'><b>{cit_score}%</b></font>", card_num_style),
            Paragraph("Citation Integrity", card_title_style),
            Paragraph("Academic verification", card_sub_style)
        ]

        metrics_table = Table(
            [[c1_content, c2_content, c3_content]],
            colWidths=[180, 180, 180]
        )
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_LIGHT),
            ('INNERGRID', (0, 0), (-1, -1), 1, BORDER_LIGHT),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 12))

        # 3. Similarity Breakdown Table
        story.append(Paragraph("Similarity Profile Breakdown", section_h1))
        breakdown_data = [
            [
                Paragraph("<b>Match Classification</b>", table_cell_bold),
                Paragraph("<b>Detection Technology</b>", table_cell_bold),
                Paragraph("<b>Sentence Count</b>", table_cell_bold),
                Paragraph("<b>Percentage</b>", table_cell_bold)
            ],
            [
                Paragraph(f"<font color='#ef4444'>&bull;</font> <b>Lexical Matching</b>", table_cell_style),
                Paragraph("Elasticsearch BM25 & Shingling", table_cell_style),
                Paragraph(str(lexical_count), table_cell_style),
                Paragraph(f"<b>{lexical_pct}%</b>", table_cell_style)
            ],
            [
                Paragraph(f"<font color='#f59e0b'>&bull;</font> <b>Hybrid Matching</b>", table_cell_style),
                Paragraph("Syntactic & Fuzzy Token Alignment", table_cell_style),
                Paragraph(str(hybrid_count), table_cell_style),
                Paragraph(f"<b>{hybrid_pct}%</b>", table_cell_style)
            ],
            [
                Paragraph(f"<font color='#8b5cf6'>&bull;</font> <b>Semantic Indexing</b>", table_cell_style),
                Paragraph("pgvector Dense Neural Embeddings", table_cell_style),
                Paragraph(str(semantic_count), table_cell_style),
                Paragraph(f"<b>{semantic_pct}%</b>", table_cell_style)
            ],
            [
                Paragraph(f"<font color='#10b981'>&bull;</font> <b>Original Content</b>", table_cell_style),
                Paragraph("Unique Scholarly Formulation", table_cell_style),
                Paragraph(str(max(0, total_sents - lexical_count - hybrid_count - semantic_count)), table_cell_style),
                Paragraph(f"<b>{original_pct}%</b>", table_cell_style)
            ]
        ]
        t_breakdown = Table(breakdown_data, colWidths=[150, 190, 100, 100])
        t_breakdown.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_breakdown)
        story.append(Spacer(1, 14))

        # 4. Top Reference Matches
        if matches:
            story.append(Paragraph("Matched Reference Sources", section_h1))
            sources_data = [
                [
                    Paragraph("<b>Source / Paper Title</b>", table_cell_bold),
                    Paragraph("<b>Author / Provenance</b>", table_cell_bold),
                    Paragraph("<b>Match Type</b>", table_cell_bold),
                    Paragraph("<b>Score</b>", table_cell_bold)
                ]
            ]
            seen_sources = set()
            for m in matches[:6]:
                ms = m.get("matched_sentence", {})
                title = ms.get("title", "Reference Corpus Document")
                if title in seen_sources:
                    continue
                seen_sources.add(title)
                mtype = m.get("match_type", "lexical").upper()
                score_val = f"{int(round(m.get('score', 0.9) * 100))}%"
                sources_data.append([
                    Paragraph(html.escape(title[:60]), table_cell_style),
                    Paragraph(html.escape(ms.get("author", "Academic Database")[:35]), table_cell_style),
                    Paragraph(mtype, table_cell_style),
                    Paragraph(score_val, table_cell_bold)
                ])

            t_sources = Table(sources_data, colWidths=[230, 150, 90, 70])
            t_sources.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t_sources)
            story.append(Spacer(1, 14))

        # 5. Document Content Flow with Highlights
        story.append(PageBreak())
        story.append(Paragraph("Annotated Document Content", section_h1))
        story.append(Paragraph("Below is the full document text with highlighted match classifications.", subtitle_style))
        story.append(Spacer(1, 6))

        matches_map = {m["query_sentence"]["start_char"]: m for m in matches if "query_sentence" in m}
        doc_paras = []
        for s in sentences:
            stext = html.escape(s.get("text", ""))
            start = s.get("start_char", 0)
            if start in matches_map:
                m = matches_map[start]
                mtype = m.get("match_type", "lexical")
                color_hex = "#ef4444" if mtype == "lexical" else ("#f59e0b" if mtype == "hybrid" else "#8b5cf6")
                doc_paras.append(f"<font color='{color_hex}'><b>[{mtype.upper()}]</b> {stext}</font>")
            else:
                doc_paras.append(stext)

        full_annotated_text = " ".join(doc_paras)
        story.append(Paragraph(full_annotated_text, body_style))
        story.append(Spacer(1, 14))

        # 6. Detailed Comparisons (if any)
        if matches:
            story.append(PageBreak())
            story.append(Paragraph("Segment-by-Segment Comparisons", section_h1))
            for i, m in enumerate(matches[:10], 1):
                qs = m.get("query_sentence", {}).get("text", "")
                ms = m.get("matched_sentence", {})
                ms_text = ms.get("text", "")
                ms_title = ms.get("title", "Corpus Document")
                mtype = m.get("match_type", "lexical").upper()
                score_pct = int(round(m.get("score", 0.9) * 100))

                comp_data = [
                    [Paragraph(f"<b>Match #{i}: {mtype} ({score_pct}% Match)</b> &mdash; <i>{html.escape(ms_title)}</i>", table_cell_bold)],
                    [Paragraph(f"<b>Query:</b> {html.escape(qs)}", table_cell_style)],
                    [Paragraph(f"<b>Source:</b> {html.escape(ms_text)}", table_cell_style)]
                ]
                t_comp = Table(comp_data, colWidths=[540])
                t_comp.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
                    ('BOX', (0, 0), (-1, -1), 1, BORDER_LIGHT),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                story.append(t_comp)
                story.append(Spacer(1, 6))

        doc.build(story)
        return buf.getvalue()

