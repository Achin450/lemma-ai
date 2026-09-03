"""
Citation Analyzer Service

Analyzes citation integrity by:
1. Detecting unsupported citations (cite claims the source doesn't support)
2. Detecting padded citations (bibliography entries never cited in text)
3. Detecting paraphrase-adjacent-to-uncited-source patterns
"""
from __future__ import annotations
import logging
from typing import Optional

from app.services.citation_parser import CitationParserService

logger = logging.getLogger(__name__)


class CitationAnalyzerService:
    """Analyzes citation integrity in academic documents."""

    @classmethod
    def analyze(
        cls,
        text: str,
        sentences: list[dict],
        plagiarism_matches: list[dict],
    ) -> dict:
        """
        Full citation integrity analysis.

        Args:
            text: Full document text.
            sentences: Segmented sentences [{text, start_char, end_char}].
            plagiarism_matches: Existing plagiarism match results from DualTierMatcher.

        Returns:
            Dict matching CitationAnalysisResult schema.
        """
        # Step 1: Parse citations and bibliography
        in_text_citations = CitationParserService.extract_in_text_citations(text)
        bibliography = CitationParserService.extract_bibliography(text)

        # Step 2: Cross-reference
        in_text_citations, bibliography = CitationParserService.cross_reference(
            in_text_citations, bibliography
        )

        # Step 3: Find padded citations (bibliography entries never cited in text)
        padded_issues = []
        for bib in bibliography:
            if not bib.get("cited_in_text"):
                padded_issues.append({
                    "issue_type": "padded_citation",
                    "severity": "medium",
                    "sentence_text": "",
                    "citation_text": bib["raw_text"][:100],
                    "explanation": (
                        f"Bibliography entry '{(bib.get('title') or bib['raw_text'][:60])}' "
                        f"does not appear to be cited anywhere in the document text. "
                        f"This may indicate citation padding."
                    ),
                    "start_char": 0,
                    "end_char": 0,
                    "suggested_fix": "Remove this entry from the bibliography, or add an in-text citation where you discuss this source.",
                })

        # Step 4: Detect uncited paraphrases
        # A sentence that has a semantic plagiarism match but NO nearby citation is suspicious
        uncited_paraphrase_issues = []
        for match in plagiarism_matches:
            if match.get("match_type") not in ("semantic", "hybrid"):
                continue  # Only check paraphrase-type matches

            sent = match["query_sentence"]
            sent_start = sent["start_char"]
            sent_end = sent["end_char"]

            # Check if any citation appears within ±300 chars of this sentence
            nearby_citations = [
                c for c in in_text_citations
                if abs(c["start_char"] - sent_start) <= 300
                or abs(c["end_char"] - sent_end) <= 300
            ]

            if not nearby_citations:
                matched_source = match["matched_sentence"]
                score_pct = int(round(match.get("score", 0) * 100))
                uncited_paraphrase_issues.append({
                    "issue_type": "uncited_paraphrase",
                    "severity": "high" if score_pct >= 75 else "medium",
                    "sentence_text": sent["text"],
                    "citation_text": None,
                    "explanation": (
                        f"This sentence has {score_pct}% semantic similarity to "
                        f"'{matched_source.get('doc_title', 'a known source')}' "
                        f"but no nearby citation was found. This may constitute uncited paraphrasing."
                    ),
                    "start_char": sent_start,
                    "end_char": sent_end,
                    "suggested_fix": (
                        f"Add a citation to '{matched_source.get('doc_title', 'the source')}' "
                        f"after this sentence, or rewrite the idea in truly original language."
                    ),
                })

        # Step 5: Unsupported citations (basic check)
        # Citations appearing in sentences that score LOW on semantic match to any source
        # are potentially unsupported (citing something that doesn't support the claim)
        unsupported_issues = []
        # Build a map of citation positions to sentences
        for cit in in_text_citations:
            cit_pos = cit["start_char"]
            # Find containing sentence
            containing = None
            for s in sentences:
                if s["start_char"] <= cit_pos <= s["end_char"]:
                    containing = s
                    break
            if containing is None:
                continue

            # Check if this sentence has any plagiarism match (if it does, the citation exists)
            has_match = any(
                m["query_sentence"]["start_char"] == containing["start_char"]
                for m in plagiarism_matches
            )

            # If the cited sentence has NO match in our corpus, the citation *might* be unsupported
            # (We can't verify it without access to the cited source, so flag as low severity)
            if not has_match and cit.get("author"):
                # Check if the author appears in our bibliography
                cit_author_lower = (cit.get("author") or "").lower().split()[0]
                bib_authors = [(b.get("author") or "").lower() for b in bibliography]
                author_in_bib = any(cit_author_lower in ba for ba in bib_authors if ba)

                if not author_in_bib and len(bibliography) > 0:
                    unsupported_issues.append({
                        "issue_type": "unsupported_citation",
                        "severity": "low",
                        "sentence_text": containing["text"],
                        "citation_text": cit["text"],
                        "explanation": (
                            f"The citation {cit['text']} does not match any bibliography entry. "
                            f"Ensure the source is listed in your references."
                        ),
                        "start_char": containing["start_char"],
                        "end_char": containing["end_char"],
                        "suggested_fix": f"Add a bibliography entry for {cit['text']} or correct the citation.",
                    })

        # Step 6: Compute citation integrity score
        total_issues = len(padded_issues) + len(uncited_paraphrase_issues) + len(unsupported_issues)
        high_issues = sum(
            1 for i in (padded_issues + uncited_paraphrase_issues + unsupported_issues)
            if i["severity"] == "high"
        )
        if total_issues == 0:
            integrity_score = 1.0
        else:
            penalty = (high_issues * 0.15) + ((total_issues - high_issues) * 0.05)
            integrity_score = max(0.0, 1.0 - penalty)

        # Summary
        if integrity_score >= 0.9:
            summary = "Citation integrity is excellent. All sources appear properly cited and supported."
        elif integrity_score >= 0.7:
            summary = f"Citation integrity is fair. {total_issues} issue(s) detected — review flagged items."
        else:
            summary = f"Citation integrity needs attention. {total_issues} issues were flagged, including {high_issues} high-severity concern(s)."

        return {
            "total_in_text_citations": len(in_text_citations),
            "total_bibliography_entries": len(bibliography),
            "citation_integrity_score": round(integrity_score, 4),
            "unsupported_citations": unsupported_issues,
            "padded_citations": padded_issues,
            "uncited_paraphrases": uncited_paraphrase_issues,
            "in_text_citations": in_text_citations,
            "bibliography_entries": bibliography,
            "summary": summary,
        }
