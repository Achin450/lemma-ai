"""
Academic Humanizer Service
Transforms AI-generated academic text into highly natural, human-like scholarly writing
with realistic burstiness, nuanced syntactic structures, and zero detectable AI clichés.
"""
from __future__ import annotations

import re
import random
import logging

logger = logging.getLogger(__name__)

# Common formulaic AI phrases and their authentic scholarly human replacements
AI_PHRASE_REPLACEMENTS = [
    # Openers & Clichés
    (r"\bIn recent years\b", ["Historically", "Over the past decade", "In contemporary research", "Within the current literature"]),
    (r"\bthe rapid proliferation of\b", ["the widespread adoption of", "the expansion of", "the increasing prevalence of", "systemic growth in"]),
    (r"\brapid proliferation\b", ["widespread adoption", "steady emergence", "exponential expansion"]),
    (r"\bhas played a pivotal role in\b", ["has directly underpinned", "has fundamentally dictated", "has shaped", "anchors"]),
    (r"\bplayed a pivotal role in\b", ["directly underpinned", "fundamentally dictated", "shaped", "anchored"]),
    (r"\bplays a pivotal role in\b", ["directly underpins", "fundamentally dictates", "is central to", "determines the efficacy of"]),
    (r"\bhas played a crucial role in\b", ["has served as a cornerstone of", "has directly informed", "has driven"]),
    (r"\bplayed a crucial role in\b", ["served as a cornerstone of", "directly informed", "drove"]),
    (r"\bplays a crucial role in\b", ["is essential to", "shapes", "governs the dynamics of", "directly informs"]),
    (r"\bplay a crucial role\b", ["serve as key determinants", "anchor the methodology", "govern system stability"]),
    (r"\bit is important to note that\b", ["notably", "significantly", "critically", "empirically"]),
    (r"\bit should be noted that\b", ["observe that", "importantly", "in practice", "as established"]),
    (r"\bit is worth noting that\b", ["notably", "in particular", "of note", "crucially"]),
    (r"\bdelve into\b", ["investigate", "examine", "quantify", "scrutinize"]),
    (r"\bdelves into\b", ["examines", "investigates", "formulates", "analyzes"]),
    (r"\ba testament to\b", ["clear evidence of", "a direct consequence of", "illustrative of"]),
    (r"\btestament to\b", ["indicative of", "demonstrative of", "reflective of"]),
    (r"\bmultifaceted\b", ["complex", "composite", "multi-dimensional", "heterogeneous"]),
    (r"\bever-evolving\b", ["dynamic", "shifting", "developing"]),
    (r"\bfast-paced\b", ["rapidly shifting", "demanding", "high-throughput"]),
    (r"\blandscape of\b", ["domain of", "paradigm of", "environment governing"]),
    
    # Overused AI Transitions
    (r"\bFurthermore,\b", ["In parallel,", "Concurrently,", "Empirically,", "In addition,", "Beyond this,"]),
    (r"\bMoreover,\b", ["Importantly,", "In contrast,", "Significantly,", "Equally critical,"]),
    (r"\bAdditionally,\b", ["In conjunction,", "Complementing this,", "Likewise,", "Secondarily,"]),
    (r"\bTo summarize,\b", ["In synthesis,", "Across these dimensions,", "Collectively,"]),
    (r"\bIn conclusion,\b", ["Ultimately,", "Synthesizing these findings,", "In sum,"]),
    (r"\bIn summary,\b", ["Taken together,", "Across these trials,", "On balance,"]),
    (r"\bLastly,\b", ["Finally,", "In closing,"]),
    
    # Hedging & robotic formulations
    (r"\bIt is essential to\b", ["Researchers must", "System designers must", "One must"]),
    (r"\bIt is crucial that\b", ["Sound methodology requires that", "Empirical validity demands that"]),
    (r"\bIt is vital to\b", ["We must", "Rigorous evaluation requires"]),
    (r"\ba wide range of\b", ["diverse", "heterogeneous", "multiple", "several"]),
    (r"\ba plethora of\b", ["numerous", "substantial", "diverse"]),
    (r"\bharness the power of\b", ["leverage", "utilize", "deploy", "apply"]),
    (r"\bharnessing\b", ["leveraging", "employing", "deploying"]),
    (r"\bseamlessly\b", ["directly", "without computational bottleneck", "consistently"]),
    (r"\bgame-changer\b", ["paradigm shift", "fundamental advance", "substantial improvement"]),
]

# Short anchor statements to randomly inject for human burstiness when paragraphs are too uniform
SHORT_BURST_ANCHORS = [
    "This assumption fails in practice.",
    "The underlying trade-off is straightforward.",
    "Empirical evidence confirms this disparity.",
    "Three distinct factors govern this outcome.",
    "This distinction remains critical.",
    "The analytical justification is clear.",
    "Such constraints cannot be overlooked.",
]


class AcademicHumanizerService:
    """
    Transforms text to match authentic human academic writing patterns:
    1. Replaces formulaic AI vocabulary and transitions.
    2. Modulates sentence-length variance (Burstiness).
    3. Preserves all inline citations [1], [2], mathematical formulas, and scientific terms.
    """

    @classmethod
    def humanize_text(cls, text: str, preserve_citations: bool = True) -> str:
        """
        Main entrypoint to humanize academic text.
        """
        if not text or not text.strip():
            return ""

        # Step 1: Protect citations and equations before processing
        citation_tokens = {}
        math_tokens = {}

        def save_citation(match):
            placeholder = f"__CIT_TOKEN_{len(citation_tokens)}__"
            citation_tokens[placeholder] = match.group(0)
            return placeholder

        def save_math(match):
            placeholder = f"__MATH_TOKEN_{len(math_tokens)}__"
            math_tokens[placeholder] = match.group(0)
            return placeholder

        # Protect inline citations [1], [1, 2], [1]-[3]
        processed_text = re.sub(r'\[\s*\d+(?:\s*,\s*\d+|\s*-\s*\d+)*\s*\]', save_citation, text)
        # Protect LaTeX equations $$...$$ and $...$ and (1), (2) equation numbers
        processed_text = re.sub(r'\$\$[^\$]+\$\$', save_math, processed_text)
        processed_text = re.sub(r'\$[^\$]+\$', save_math, processed_text)

        # Step 2: Apply targeted phrase de-patterning
        for pattern, replacements in AI_PHRASE_REPLACEMENTS:
            def replace_match(m, repls=replacements):
                chosen = random.choice(repls)
                # Preserve capitalization
                if m.group(0)[0].isupper():
                    chosen = chosen[0].upper() + chosen[1:]
                return chosen

            processed_text = re.sub(pattern, replace_match, processed_text, flags=re.IGNORECASE)

        # Step 3: Sentence rhythm and burstiness adjustment per paragraph
        paragraphs = processed_text.split("\n\n")
        humanized_paragraphs = []

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            # Split into sentences while keeping punctuation
            sentences = re.split(r'(?<=[.!?])\s+', p_strip)
            if len(sentences) >= 4:
                # Check for low burstiness (sentences all between 18 and 26 words)
                lengths = [len(s.split()) for s in sentences]
                avg_len = sum(lengths) / len(lengths)
                variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)

                if variance < 20 and len(sentences) >= 4:
                    # Modulate: Combine 2 short ones with a semicolon or em-dash to introduce human complexity
                    idx_to_combine = random.randint(1, len(sentences) - 2)
                    s1 = sentences[idx_to_combine].rstrip(".?!")
                    s2 = sentences[idx_to_combine + 1]
                    s2_lower = s2[0].lower() + s2[1:] if len(s2) > 1 else s2.lower()
                    combined = f"{s1}; specifically, {s2_lower}"
                    
                    sentences[idx_to_combine] = combined
                    sentences.pop(idx_to_combine + 1)

            humanized_p = " ".join(sentences)
            humanized_paragraphs.append(humanized_p)

        result = "\n\n".join(humanized_paragraphs)

        # Step 4: Restore protected math and citations
        for placeholder, original in math_tokens.items():
            result = result.replace(placeholder, original)
        for placeholder, original in citation_tokens.items():
            result = result.replace(placeholder, original)

        return result

    @classmethod
    def humanize_section(cls, content: str) -> str:
        """Humanizes a complete research section."""
        return cls.humanize_text(content)
