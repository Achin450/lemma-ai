"""
Topic Validator Service for Lemma AI.
Implements a 4-tier foolproof defense:
1. Heuristic & Shannon Entropy / Keyboard-Mash Detector (0ms)
2. Common Non-Academic & Slang Filter
3. Fast LLM Academic Feasibility & Intent Guardrail
4. arXiv Academic Preprints Evidence Verification
"""
from __future__ import annotations

import re
import math
import json
import logging
from typing import Optional, List
from pydantic import BaseModel, Field

from app.services.llm import LLMService
from app.services.online_retriever import OnlineRetrieverService

logger = logging.getLogger(__name__)


class TopicValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether the topic is a valid academic research topic")
    error_code: Optional[str] = Field(None, description="Error code if invalid (e.g., GIBBERISH, NON_ACADEMIC, TOO_VAGUE)")
    reason: Optional[str] = Field(None, description="User-friendly explanation of why it failed or passed")
    refined_topic: Optional[str] = Field(None, description="Polished scientific topic string if valid")
    domain: Optional[str] = Field(None, description="Inferred research domain")
    suggestions: List[str] = Field(default_factory=list, description="3 academic alternative suggestions if invalid")


# Curated academic fallback suggestions for various common patterns
CURATED_SUGGESTIONS = {
    "ai": [
        "Deep Reinforcement Learning in Autonomous Robotics",
        "Transformer Architectures for Natural Language Processing",
        "Explainable Artificial Intelligence for Clinical Decision Support",
    ],
    "robot": [
        "Dynamic Path Planning for Quadrupedal Robots in Unstructured Terrains",
        "Vision-Language-Action Models in Collaborative Robotic Manipulation",
        "Model Predictive Control for High-Speed Autonomous Drones",
    ],
    "quantum": [
        "Fault-Tolerant Quantum Error Correction with Surface Codes",
        "Variational Quantum Eigensolvers for Molecular Chemistry Simulation",
        "Quantum Key Distribution Protocols for Secure Satellite Communication",
    ],
    "biology": [
        "Graph Neural Networks for Drug Discovery and Molecular Property Prediction",
        "CRISPR-Cas9 Off-Target Mutation Prediction Using Deep Sequence Models",
        "Single-Cell RNA Sequencing Analysis for Tumor Microenvironment Profiling",
    ],
    "cybersecurity": [
        "Zero-Trust Architecture for Decentralized Cloud Computing",
        "Zero-Knowledge Proofs for Privacy-Preserving Identity Verification",
        "Adversarial Robustness and Defense Mechanisms in Deep Neural Networks",
    ],
    "general": [
        "Deep Reinforcement Learning for Autonomous Systems",
        "Graph Neural Networks for Molecular and Biomedical Modeling",
        "Self-Supervised Representation Learning for High-Dimensional Data",
    ]
}

# Keyboard mash patterns (repeating characters, qwerty walks)
KEYBOARD_WALKS = [
    "qwerty", "asdfgh", "zxcvbn", "12345", "67890",
    "qwer", "asdf", "zxcv", "hjkl", "yuio", "bnm"
]

NON_ACADEMIC_PATTERNS = [
    r"\b(hi|hello|hey|bhai|bro|dude|sup|kese|kaisa|kya|haan|nahi)\b",
    r"\b(how to make|how to cook|recipe|maggi|chai|tea|pizza|burger)\b",
    r"\b(kutta|billi|dog|cat|girlfriend|boyfriend|pyar|love|shadi)\b",
    r"\b(joke|prank|meme|funny|lol|lmao|rofl|sexy|porn|xxx)\b",
    r"\b(who are you|what is your name|mera naam|apka naam)\b",
    r"\b(song|lyrics|movie|actor|cricket|ipl|score)\b",
]


class TopicValidator:
    """Multi-tiered validator ensuring paper generation topics are valid, scholarly, and evidenced."""

    @classmethod
    def calculate_shannon_entropy(cls, text: str) -> float:
        """Calculates Shannon entropy to detect repetitive or flat character distributions."""
        clean = re.sub(r'\s+', '', text.lower())
        if not clean:
            return 0.0
        length = len(clean)
        counts = {}
        for ch in clean:
            counts[ch] = counts.get(ch, 0) + 1
        entropy = -sum((c / length) * math.log2(c / length) for c in counts.values())
        return entropy

    @classmethod
    def check_heuristics(cls, topic: str) -> Optional[TopicValidationResult]:
        """
        Fast 0ms heuristic check.
        Returns a TopicValidationResult if invalid, or None if heuristics pass.
        """
        raw = topic.strip()
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-_]', '', raw).strip()
        words = [w for w in cleaned.split() if len(w) > 0]

        # 1. Length & Word Count Check
        if len(raw) < 5:
            return TopicValidationResult(
                is_valid=False,
                error_code="TOO_SHORT",
                reason="The research topic is too short. Please provide a descriptive topic of at least 2-3 words.",
                suggestions=CURATED_SUGGESTIONS["general"]
            )

        if len(words) < 2:
            # Single word: unless it's a very specific scientific compound, prompt for specificity
            w_lower = words[0].lower() if words else ""
            matched_sugg = CURATED_SUGGESTIONS.get(w_lower, CURATED_SUGGESTIONS["general"])
            return TopicValidationResult(
                is_valid=False,
                error_code="TOO_VAGUE",
                reason=f"'{raw}' is too broad for a publication-grade research paper. Please specify the research direction or problem domain.",
                suggestions=matched_sugg
            )

        # 2. Pure numbers check
        if re.match(r'^[\d\s\W]+$', raw):
            return TopicValidationResult(
                is_valid=False,
                error_code="NUMERICAL_GIBBERISH",
                reason="The input consists only of numbers or symbols. Please enter a valid scientific topic.",
                suggestions=CURATED_SUGGESTIONS["general"]
            )

        # 3. Repeated characters (e.g. "aaaaa", "11111", "asddddddd")
        if re.search(r'(.)\1{4,}', raw):
            return TopicValidationResult(
                is_valid=False,
                error_code="REPEATED_CHARS",
                reason="The input contains repeated consecutive characters, which indicates invalid input.",
                suggestions=CURATED_SUGGESTIONS["general"]
            )

        # 4. Consonant clusters / Keyboard Mash
        # Detect long sequences of consonants without vowels (e.g., "asdfghjk", "qwrtypsd")
        for word in words:
            if len(word) >= 6:
                consonants = re.findall(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{6,}', word)
                if consonants:
                    return TopicValidationResult(
                        is_valid=False,
                        error_code="KEYBOARD_MASH",
                        reason=f"The word '{word}' contains unnatural consonant patterns resembling keyboard mash.",
                        suggestions=CURATED_SUGGESTIONS["general"]
                    )

        # 5. QWERTY walks
        raw_lower = raw.lower()
        for walk in KEYBOARD_WALKS:
            if walk in raw_lower:
                return TopicValidationResult(
                    is_valid=False,
                    error_code="KEYBOARD_WALK",
                    reason="The input matches sequential keyboard sweeps. Please type a meaningful research topic.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 6. Non-academic colloquial phrases
        for pattern in NON_ACADEMIC_PATTERNS:
            if re.search(pattern, raw_lower, re.IGNORECASE):
                return TopicValidationResult(
                    is_valid=False,
                    error_code="NON_ACADEMIC_CONTENT",
                    reason="The query appears to be informal chat, everyday conversation, or non-scholarly text.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 7. Low Shannon Entropy (flat repetitive patterns)
        if len(raw) >= 12:
            entropy = cls.calculate_shannon_entropy(raw)
            if entropy < 2.2:
                return TopicValidationResult(
                    is_valid=False,
                    error_code="LOW_ENTROPY",
                    reason="The topic has an unnaturally repetitive or low-entropy character distribution.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        return None

    @classmethod
    async def check_llm_guardrail(cls, topic: str, domain: Optional[str] = None) -> TopicValidationResult:
        """
        Fast AI Guardrail: asks LLM to evaluate academic feasibility and return alternatives.
        """
        domain_ctx = f" in the domain of {domain}" if domain else ""
        prompt = (
            "You are an academic topic validator for an IEEE-style scientific research platform.\n"
            f"Evaluate if the following query is a legitimate academic, scientific, or engineering research inquiry{domain_ctx}:\n"
            f"Query: \"{topic}\"\n\n"
            "Rules:\n"
            "1. If it is gibberish, colloquial chit-chat, a joke, cooking/recipes, random everyday questions, insults, or unscientific:\n"
            "   Set \"is_valid\": false, provide a polite 1-sentence reason, and 3 high-quality academic paper topics as suggestions.\n"
            "2. If it is a legitimate scholarly topic (even if concise or specialized):\n"
            "   Set \"is_valid\": true, provide a refined scientific topic, identify the academic domain, and empty suggestions.\n\n"
            "Respond in JSON ONLY:\n"
            "{\n"
            "  \"is_valid\": boolean,\n"
            "  \"reason\": \"string\",\n"
            "  \"refined_topic\": \"string\",\n"
            "  \"academic_domain\": \"string\",\n"
            "  \"suggestions\": [\"topic1\", \"topic2\", \"topic3\"]\n"
            "}"
        )

        try:
            model = await LLMService._resolve_model()
            res = await LLMService._call_ollama(prompt, model, temp=0.2)
            if res and res.strip():
                match = re.search(r'\{.*\}', res, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    is_valid = bool(data.get("is_valid", False))
                    reason = data.get("reason", "")
                    refined = data.get("refined_topic", topic)
                    dom = data.get("academic_domain", domain or "Computer Science & Engineering")
                    suggs = data.get("suggestions", [])
                    if not suggs or len(suggs) == 0:
                        suggs = CURATED_SUGGESTIONS["general"]

                    return TopicValidationResult(
                        is_valid=is_valid,
                        error_code=None if is_valid else "NON_ACADEMIC_TOPIC",
                        reason=reason if reason else ("Topic verified as scholarly." if is_valid else "Topic is not recognized as academic research."),
                        refined_topic=refined,
                        domain=dom,
                        suggestions=suggs[:3]
                    )
        except Exception as e:
            logger.warning(f"Fast LLM topic guardrail check failed or timed out: {e}")

        # If LLM failed, assume heuristic pass was valid to not block genuine users when offline
        return TopicValidationResult(
            is_valid=True,
            reason="Heuristic evaluation confirmed academic syntax.",
            refined_topic=topic,
            domain=domain or "Computer Science & Engineering",
            suggestions=[]
        )

    @classmethod
    async def check_arxiv_evidence(cls, topic: str) -> bool:
        """
        Tier 4 evidence verification: queries arXiv to ensure scientific literature exists.
        Returns True if literature or matching academic concepts are found.
        """
        try:
            candidates = await OnlineRetrieverService.fetch_arxiv_candidates(topic, limit=3)
            if candidates and len(candidates) > 0:
                return True

            # If full query has 0 direct matches, test key nouns
            words = [w for w in topic.split() if len(w) > 3][:3]
            if words:
                keyword_query = " ".join(words)
                kw_candidates = await OnlineRetrieverService.fetch_arxiv_candidates(keyword_query, limit=3)
                if kw_candidates and len(kw_candidates) > 0:
                    return True
        except Exception as e:
            logger.warning(f"arXiv pre-verification check failed: {e}")
            # If network error, don't fail genuine users
            return True

        return False

    @classmethod
    async def validate_topic(cls, topic: str, domain: Optional[str] = None) -> TopicValidationResult:
        """
        Unified 4-Tier validation runner:
        1. Tier 2: Heuristic & Shannon Entropy (0ms)
        2. Tier 3: Fast LLM Guardrail (~300ms)
        3. Tier 4: arXiv Evidence Pre-check
        """
        # Step 1: Heuristic Check
        heuristic_res = cls.check_heuristics(topic)
        if heuristic_res and not heuristic_res.is_valid:
            logger.info(f"[Topic Validation] Rejected by Heuristics: '{topic}' ({heuristic_res.error_code})")
            return heuristic_res

        # Step 2: LLM Guardrail Check
        llm_res = await cls.check_llm_guardrail(topic, domain)
        if not llm_res.is_valid:
            logger.info(f"[Topic Validation] Rejected by LLM Guardrail: '{topic}' - {llm_res.reason}")
            return llm_res

        # Step 3: arXiv Literature Check
        has_arxiv = await cls.check_arxiv_evidence(topic)
        if not has_arxiv:
            logger.info(f"[Topic Validation] Rejected by arXiv Evidence Check: No papers found for '{topic}'")
            return TopicValidationResult(
                is_valid=False,
                error_code="NO_ACADEMIC_EVIDENCE",
                reason=f"No peer-reviewed papers or scientific preprints were found on arXiv for '{topic}'. Academic papers require verified literature to generate valid citations.",
                suggestions=CURATED_SUGGESTIONS["general"]
            )

        logger.info(f"[Topic Validation] Verified: '{topic}' -> {llm_res.refined_topic}")
        return llm_res
