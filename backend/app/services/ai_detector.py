"""
AI-Generated Text Detection Service

Detects AI-generated text using three complementary methods:
1. Perplexity Scoring: LM-based token probability (low perplexity = AI-like uniformity)
2. Burstiness Analysis: Sentence-length variance (low burstiness = AI-like uniformity)
3. Fingerprint Detection: Pattern-matching against known AI output signatures

Designed to run locally without external API calls.
"""
from __future__ import annotations
import re
import math
import logging
import statistics
from typing import Optional

logger = logging.getLogger(__name__)

# Known AI output patterns — common in ChatGPT/Claude/Gemini outputs
AI_FINGERPRINTS = [
    # Opening patterns
    (r"^(certainly|absolutely|of course|sure|great question|as an ai)",
     "Common AI acknowledgment opener"),
    (r"^(in (today\'s|the modern|our) (world|society|era|age|landscape))",
     "Generic AI scene-setting opener"),
    (r"^(it is (important|worth noting|essential|crucial) (to|that))",
     "AI hedging opener"),
    # Transitional phrases
    (r"(furthermore|moreover|additionally|in conclusion|to summarize|in summary)",
     "Over-use of formal AI transitions"),
    (r"(it is worth noting that|it should be noted that|it is important to note)",
     "AI hedging phrase"),
    # Structural patterns
    (r"(firstly|secondly|thirdly|lastly|finally)[,\.]",
     "Formulaic AI enumeration"),
    (r"(in (this|the following) (essay|paper|article|discussion|analysis))",
     "AI essay framing"),
    # Common AI conclusions
    (r"(in (conclusion|summary), (it is|we can|one can) (see|observe|conclude|say))",
     "Formulaic AI conclusion"),
    # Excessive hedging
    (r"(it is possible that|it may be argued that|one might suggest)",
     "Excessive AI epistemic hedging"),
]


class AIDetectorService:
    """Detects AI-generated text using statistical and pattern-based methods."""

    # Lazy-loaded language model for perplexity
    _model = None
    _tokenizer = None
    _model_loaded = False

    @classmethod
    def _try_load_model(cls):
        """Attempt to load GPT-2 for perplexity scoring. Falls back gracefully."""
        if cls._model_loaded:
            return cls._model is not None
        cls._model_loaded = True
        try:
            import torch
            from transformers import GPT2LMHeadModel, GPT2TokenizerFast
            logger.info("Loading GPT-2 model for AI detection perplexity scoring...")
            cls._tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
            cls._model = GPT2LMHeadModel.from_pretrained("gpt2")
            cls._model.eval()
            logger.info("GPT-2 loaded successfully for AI detection.")
            return True
        except Exception as e:
            logger.warning(f"Could not load GPT-2 for perplexity scoring: {e}. "
                           f"Falling back to statistical-only AI detection.")
            cls._model = None
            cls._tokenizer = None
            return False

    @classmethod
    def compute_perplexity(cls, text: str) -> float:
        """
        Compute the perplexity of a text fragment using GPT-2.
        Lower perplexity → more predictable → more likely AI-generated.
        Returns a fallback heuristic score if GPT-2 is unavailable.
        """
        if not cls._try_load_model() or not text.strip():
            # Fallback: estimate perplexity from vocab richness (inverse TTR)
            tokens = text.lower().split()
            if not tokens:
                return 100.0
            ttr = len(set(tokens)) / len(tokens)
            # Low TTR → low perplexity heuristic
            return max(5.0, 50.0 * ttr)

        try:
            import torch
            inputs = cls._tokenizer(
                text, return_tensors="pt", truncation=True, max_length=512
            )
            with torch.no_grad():
                outputs = cls._model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss
            return float(math.exp(loss.item()))
        except Exception as e:
            logger.debug(f"Perplexity computation failed: {e}")
            tokens = text.lower().split()
            if not tokens:
                return 100.0
            ttr = len(set(tokens)) / len(tokens)
            return max(5.0, 50.0 * ttr)

    @classmethod
    def compute_burstiness(cls, sentences: list[str]) -> float:
        """
        Compute burstiness from sentence-length variance.
        Burstiness B = (std - mean) / (std + mean)  (ranges roughly -1 to +1)
        AI text has low burstiness (very uniform sentence lengths).
        We normalise to 0.0 (very bursty/human) to 1.0 (very uniform/AI).
        """
        if len(sentences) < 3:
            return 0.5  # Not enough data
        lengths = [len(s.split()) for s in sentences if s.strip()]
        if not lengths or statistics.mean(lengths) == 0:
            return 0.5
        mean_l = statistics.mean(lengths)
        try:
            std_l = statistics.stdev(lengths)
        except Exception:
            return 0.5
        # Burstiness: high std relative to mean = human; low = AI
        cv = std_l / mean_l  # Coefficient of variation
        # Map: cv >= 0.5 → 0.0 (bursty/human), cv <= 0.1 → 1.0 (uniform/AI)
        ai_uniform_score = max(0.0, min(1.0, 1.0 - (cv / 0.5)))
        return round(ai_uniform_score, 4)

    @classmethod
    def check_fingerprints(cls, text: str) -> list[str]:
        """
        Pattern-match the text against known AI output signatures.
        Returns a list of matched pattern descriptions.
        """
        text_lower = text.lower()
        matches = []
        for pattern, description in AI_FINGERPRINTS:
            if re.search(pattern, text_lower):
                matches.append(description)
        return matches

    @classmethod
    def sentence_ai_probability(cls, sentence_perplexity: float, doc_mean_perplexity: float) -> float:
        """
        Convert a sentence's perplexity to an AI probability.
        A sentence with perplexity much lower than the document mean is more AI-like.
        """
        if doc_mean_perplexity == 0:
            return 0.5
        ratio = sentence_perplexity / doc_mean_perplexity
        # ratio < 1 → lower than mean → more AI-like → higher probability
        if ratio <= 0.5:
            return 0.9
        elif ratio <= 0.75:
            return 0.75
        elif ratio <= 1.0:
            return 0.5
        elif ratio <= 1.5:
            return 0.25
        else:
            return 0.1

    @classmethod
    def analyze_document(
        cls,
        text: str,
        sentences: list[dict],
    ) -> dict:
        """
        Full AI detection analysis for a document.
        Returns a dict matching the AIDetectionResult schema.

        Args:
            text: Full document text.
            sentences: List of sentence dicts with {text, start_char, end_char}.
        """
        if not text.strip() or not sentences:
            return {
                "ai_score": 0.0,
                "confidence": "Likely Human",
                "perplexity_score": 100.0,
                "burstiness_score": 0.0,
                "fingerprint_matches": [],
                "sentence_level_scores": [],
                "flagged_sentence_count": 0,
                "total_sentence_count": 0,
            }

        sentence_texts = [s["text"] for s in sentences]

        # 1. Fast Document & Sentence Perplexity scoring
        # If document is large, compute overall text perplexity and estimate per-sentence variation efficiently
        doc_sample = " ".join(sentence_texts[:20])
        doc_base_perplexity = cls.compute_perplexity(doc_sample)

        sentence_perplexities = []
        # For small documents (<= 25 sentences), evaluate GPT-2 directly; for larger docs, evaluate statistically around doc_base_perplexity
        if len(sentence_texts) <= 25:
            for s_text in sentence_texts:
                ppl = cls.compute_perplexity(s_text)
                sentence_perplexities.append(ppl)
        else:
            for s_text in sentence_texts:
                tokens = s_text.lower().split()
                if not tokens:
                    sentence_perplexities.append(doc_base_perplexity)
                    continue
                ttr = len(set(tokens)) / len(tokens)
                # Calibrate sentence perplexity relative to doc base
                adj_factor = 0.5 + ttr
                sentence_perplexities.append(round(doc_base_perplexity * adj_factor, 2))

        doc_mean_perplexity = statistics.mean(sentence_perplexities) if sentence_perplexities else 100.0

        # 2. Burstiness of the whole document
        burstiness = cls.compute_burstiness(sentence_texts)

        # 3. Fingerprint detection on full text
        fingerprint_matches = cls.check_fingerprints(text)

        # 4. Per-sentence AI scores
        sentence_scores = []
        flagged_count = 0
        for s, ppl in zip(sentences, sentence_perplexities):
            ai_prob = cls.sentence_ai_probability(ppl, doc_mean_perplexity)
            if ai_prob >= 0.65:
                flagged_count += 1
            sentence_scores.append({
                "text": s["text"],
                "start_char": s["start_char"],
                "end_char": s["end_char"],
                "perplexity": round(ppl, 2),
                "ai_probability": round(ai_prob, 4),
            })

        # 5. Composite AI score
        # Weights: perplexity (0.5), burstiness (0.3), fingerprints (0.2)
        # Perplexity → normalise: very low (<20) maps to high AI prob
        if doc_mean_perplexity <= 20:
            perplexity_ai_score = 0.9
        elif doc_mean_perplexity <= 40:
            perplexity_ai_score = 0.7
        elif doc_mean_perplexity <= 80:
            perplexity_ai_score = 0.4
        elif doc_mean_perplexity <= 150:
            perplexity_ai_score = 0.2
        else:
            perplexity_ai_score = 0.05

        fingerprint_score = min(1.0, len(fingerprint_matches) / 3.0) * 0.8
        sentence_flagged_ratio = flagged_count / len(sentences) if sentences else 0.0

        ai_score = (
            0.45 * perplexity_ai_score +
            0.25 * burstiness +
            0.15 * fingerprint_score +
            0.15 * sentence_flagged_ratio
        )
        ai_score = round(min(1.0, max(0.0, ai_score)), 4)

        # 6. Confidence classification
        if ai_score >= 0.65:
            confidence = "Likely AI-Generated"
        elif ai_score >= 0.40:
            confidence = "Possibly AI-Assisted"
        else:
            confidence = "Likely Human"

        return {
            "ai_score": ai_score,
            "confidence": confidence,
            "perplexity_score": round(doc_mean_perplexity, 2),
            "burstiness_score": burstiness,
            "fingerprint_matches": fingerprint_matches,
            "sentence_level_scores": sentence_scores,
            "flagged_sentence_count": flagged_count,
            "total_sentence_count": len(sentences),
        }
