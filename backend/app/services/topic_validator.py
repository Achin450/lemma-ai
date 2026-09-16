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

CHATBOT_COMMAND_PATTERNS = [
    r"^(write|compose|draft|generate|create|make|produce)\s+(me\s+)?(an?\s+)?(paper|research\s+paper|essay|story|article|paragraph|poem|blog|letter|script|summary|speech|assignment|notes|review|report|code|program)\b",
    r"^(can\s+you|could\s+you|please|plz|kindly|will\s+you|would\s+you)\s+(write|help|give|tell|make|generate|code|solve|explain|create|show|do)\b",
    r"^(how\s+to|how\s+can\s+i|how\s+do\s+i|ways\s+to|steps\s+to)\s+(make|cook|bake|prepare|hack|crack|bypass|earn|get|buy|sell|lose|gain|impress|flirt|download|install|fix|repair|jailbreak|cheat|watch|find)\b",
    r"^(tell\s+me|show\s+me|give\s+me|explain\s+to\s+me|teach\s+me)\s+(about|how|why|what|a\s+story|a\s+joke|some|tips|tricks|steps)\b",
    r"^(what\s+is|who\s+is|where\s+is|when\s+is|which\s+is)\s+(your|my|the\s+best|the\s+top|the\s+cheapest|the\s+price|the\s+weather|the\s+score|a\s+good|a\s+cheap)\b",
    r"^(i\s+want|i\s+need|help\s+me)\s+(to\s+know|to\s+learn|to\s+write|to\s+make|to\s+cook|with\s+my|you\s+to)\b",
    r"^(do\s+my|finish\s+my|solve\s+my)\s+(homework|assignment|exam|quiz|math|project)\b",
    r"^(translate|summarize|paraphrase|rewrite)\s+(this|the\s+following|in|into)\b",
    r"^(solve|calculate|evaluate)\s+(the\s+equation|for\s+x|this\s+math|\d+)\b",
]

NON_ACADEMIC_PATTERNS = [
    # Slang & Chit-chat (English & Hinglish)
    r"\b(hi|hello|hey|heyya|hola|yo|sup|dude|bhai|bro|broda|yaar|boss|sir|madam|kese\s+ho|kaisa\s+hai|kaise\s+ho|kya\s+hal|kya\s+chal|haan|nahi|nahin|accha|theek|sahi|pagal|chutiya|bakwas|timepass|shukriya|dhanyawad|thanks|thank\s+you|good\s+morning|good\s+night|gud\s+mrng|gm|gn)\b",
    # Recipes & Everyday Cooking
    r"\b(recipe|recipes|cook\s+food|how\s+to\s+cook|maggi|chai|tea|coffee|pizza|burger|pasta|biryani|curry|samosa|momos|sandwich|paneer|chicken\s+tikka|breakfast|lunch|dinner|tasty\s+food|delicious\s+food|yummy)\b",
    # Casual Entertainment, Pop Culture, Music, Movies, Celebrities
    r"\b(movie|movies|cinema|film\s+review|song|songs|lyrics|singer|singers|actor|actress|bollywood|hollywood|netflix|hotstar|prime\s+video|anime|manga|naruto|goku|marvel|avengers|batman|spiderman|superman|disney|trailer|box\s+office|celebrity|celebrities)\b",
    # Casual Sports & Betting
    r"\b(cricket\s+match|ipl\s+match|ipl\s+202\d|bcci|icc|world\s+cup|virat\s+kohli|ms\s+dhoni|rohit\s+sharma|messi|ronaldo|football\s+match|fifa|badminton|tennis|match\s+score|live\s+score|dream11|my11circle|betting|satta|gambling|casino|lottery)\b",
    # Casual Video Gaming & Cheats
    r"\b(pubg|bgmi|free\s+fire|gta\s*5|gta\s*v|gta\s*6|fortnite|minecraft|valorant|call\s+of\s+duty|cod\s+warzone|roblox|gameplay|walkthrough|cheat\s+codes?|aimbot|esports\s+tournament)\b",
    # Casual Dating, Romance, Family & Personal
    r"\b(girlfriend|boyfriend|gf|bf|crush|breakup|dating|tinder|bumble|shaadi|shadi|marriage\s+advice|wedding|proposal|propose\s+a\s+girl|love\s+letter|love\s+story|flirt|romantic|husband|wife|divorce)\b",
    # Adult, Vulgar & Explicit
    r"\b(porn|pornography|xxx|sex|sexy|nude|nudes|boobs|penis|vagina|erotic|adult\s+video|leaked\s+mms|strip)\b",
    # Money-Making & Financial Scams
    r"\b(make\s+money\s+online|earn\s+money\s+online|earn\s+daily|free\s+crypto|free\s+bitcoin|get\s+rich\s+quick|easy\s+money|passive\s+income\s+fast|quick\s+cash|ponzi|binary\s+options|stock\s+tips|trading\s+calls)\b",
    # Hacking, Cracking & Piracy
    r"\b(hack\s+wifi|crack\s+wifi|wifi\s+password|hack\s+instagram|hack\s+facebook|hack\s+whatsapp|free\s+netflix|pirated|crack\s+software|torrent\s+download|keygen|serial\s+key|free\s+recharge)\b",
    # Casual Fitness, Diet, Beauty, Astrology
    r"\b(lose\s+weight\s+fast|lose\s+belly\s+fat|abs\s+workout|gym\s+workout\s+routine|diet\s+plan\s+for\s+weight\s+loss|skin\s+whitening|acne\s+cure|horoscope|rashifal|astrology\s+prediction|zodiac\s+sign|kundali|vastu|tarot\s+card)\b",
    # Shopping & Commercial Deals
    r"\b(best\s+phone\s+under|best\s+laptop\s+under|cheap\s+flights|discount\s+coupon|promo\s+code|flipkart\s+sale|amazon\s+sale|unboxing\s+video|review\s+of\s+iphone)\b",
]

ACADEMIC_ANCHORS = {
    # Methodological / Scientific inquiry
    "analysis", "analytical", "algorithm", "algorithms", "algorithmic", "framework", "frameworks",
    "model", "models", "modeling", "modelling", "optimization", "optimisation", "empirical",
    "evaluation", "investigation", "synthesis", "architecture", "architectures", "methodology",
    "methodologies", "paradigm", "paradigms", "simulation", "simulations", "benchmark",
    "benchmarks", "systematic", "theoretical", "experimental", "assessment", "comparative",
    "quantitative", "qualitative", "statistical", "probabilistic", "stochastic", "heuristic",
    "protocol", "protocols", "validation", "verification", "hypothesis", "survey", "taxonomy",
    # Computer Science & AI
    "neural", "network", "networks", "deep", "learning", "machine", "artificial", "intelligence",
    "transformer", "transformers", "reinforcement", "supervised", "unsupervised", "semi-supervised",
    "computational", "cryptography", "cryptographic", "blockchain", "decentralized", "cybersecurity",
    "autonomous", "robotics", "robotic", "kinematics", "mechatronics", "distributed", "parallel",
    "scalable", "scalability", "latency", "throughput", "bandwidth", "infrastructure", "microservices",
    "detection", "segmentation", "classification", "regression", "clustering", "federated",
    "hyperparameter", "convolutional", "recurrent", "lstm", "attention", "diffusion", "generative",
    "graph", "graphs", "ontology", "ontologies", "consensus", "zero-knowledge", "fault-tolerant",
    "cloud", "edge", "iot", "sensor", "sensors", "database", "query", "compiler",
    "microprocessor", "vlsi", "fpga", "embedded", "firmware", "kernel", "operating", "software",
    # Physics, Chemistry, Materials
    "quantum", "photovoltaic", "perovskite", "semiconductor", "semiconductors", "thermodynamic",
    "aerodynamic", "electromagnetic", "spectroscopy", "fluorescence", "microscopy", "photonic",
    "superconducting", "nanotechnology", "nanoparticles", "graphene", "polymer", "polymers",
    "catalysis", "catalytic", "crystallography", "spectrometry", "diffraction", "plasma",
    "thermodynamics", "optics", "quantum-resistant", "neuromorphic",
    # Biology, Medicine, Healthcare
    "genomic", "genomics", "biomedical", "molecular", "cellular", "protein", "proteins", "dna",
    "rna", "crispr", "oncology", "pathology", "clinical", "diagnostic", "therapeutics", "pharmacology",
    "epidemiology", "neuroscience", "cognitive", "biomechanical", "biocompatible", "biodegradable",
    "physiological", "pathogen", "mutation", "immunology", "pharmacokinetics", "cardiovascular",
    "metabolism", "metabolic", "microbiome", "sequencing",
    # Mathematics & Engineering
    "calculus", "differential", "integral", "algebraic", "topology", "manifold", "matrix",
    "eigenvalue", "eigenvector", "tensor", "tensors", "convex", "gradient", "convergence",
    "asymptotic", "dynamical", "fourier", "wavelet", "laplace", "finite-element", "fluid",
    "mechanics", "acoustics", "telecommunications", "signal",
    # Economics, Law, Social Sciences
    "econometrics", "macroeconomic", "microeconomic", "jurisprudence", "constitutional",
    "sociological", "ethnographic", "psycholinguistics", "governance", "policy", "monetary",
    "inflation", "fiscal", "equilibrium", "game-theoretic", "socioeconomic", "geopolitical"
}

ACADEMIC_PHRASES = [
    r"\b(investigation\s+of|comparative\s+study|empirical\s+analysis|systematic\s+review|impact\s+of|role\s+of|performance\s+evaluation|design\s+and\s+implementation|applications?\s+of|advancements?\s+in|challenges\s+and\s+opportunities|state\s+of\s+the\s+art|a\s+novel\s+approach|theoretical\s+framework|experimental\s+assessment|influence\s+of|efficacy\s+of|optimization\s+of|synthesis\s+of|modeling\s+of|mitigation\s+of|assessment\s+of|characterization\s+of|mechanism\s+of|formulation\s+of)\b"
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
        raw_lower = raw.lower()

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
        for walk in KEYBOARD_WALKS:
            if walk in raw_lower:
                return TopicValidationResult(
                    is_valid=False,
                    error_code="KEYBOARD_WALK",
                    reason="The input matches sequential keyboard sweeps. Please type a meaningful research topic.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 6. Conversational Chatbot Commands
        for pattern in CHATBOT_COMMAND_PATTERNS:
            if re.search(pattern, raw_lower, re.IGNORECASE):
                return TopicValidationResult(
                    is_valid=False,
                    error_code="CHATBOT_PROMPT",
                    reason="Conversational instructions (e.g., 'write an essay', 'how to') are not valid paper topics. Please provide a formal scientific title.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 7. Non-academic colloquial phrases & domains
        for pattern in NON_ACADEMIC_PATTERNS:
            if re.search(pattern, raw_lower, re.IGNORECASE):
                return TopicValidationResult(
                    is_valid=False,
                    error_code="NON_ACADEMIC_CONTENT",
                    reason="The query appears to be informal chat, everyday lifestyle, or non-scholarly text.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 8. Low Shannon Entropy (flat repetitive patterns)
        if len(raw) >= 12:
            entropy = cls.calculate_shannon_entropy(raw)
            if entropy < 2.2:
                return TopicValidationResult(
                    is_valid=False,
                    error_code="LOW_ENTROPY",
                    reason="The topic has an unnaturally repetitive or low-entropy character distribution.",
                    suggestions=CURATED_SUGGESTIONS["general"]
                )

        # 9. Academic Substance Check for short or casual queries
        has_phrase = any(re.search(p, raw_lower, re.IGNORECASE) for p in ACADEMIC_PHRASES)
        has_anchor = any(w.lower() in ACADEMIC_ANCHORS for w in words)
        if not has_phrase and not has_anchor:
            return TopicValidationResult(
                is_valid=False,
                error_code="LACKS_ACADEMIC_SUBSTANCE",
                reason="The query lacks recognized academic or scientific context. Please provide a specific scholarly topic or research question.",
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
            # Try Cloud LLM first (Groq/OpenAI) or local Ollama
            res = await LLMService._call_cloud_llm(prompt, temp=0.2)
            if not res:
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

        # When offline or LLM unreachable, heuristic evaluation already passed
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

            # Stop words to exclude from fallback keyword queries
            STOP_WORDS = {
                "write", "paper", "essay", "make", "cook", "good", "best", "some", "with",
                "from", "that", "this", "what", "which", "when", "where", "have", "been",
                "will", "about", "into", "more", "other", "than", "then", "them", "these",
                "many", "most", "also", "such", "like", "over", "even", "only", "just", "code"
            }
            words = [w.lower() for w in topic.split() if len(w) > 3 and w.lower() not in STOP_WORDS][:3]
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
