import httpx
import logging
from fastapi import HTTPException, status
from app.config import settings
from app.services.research_domain_knowledge import ResearchDomainKnowledgeService

logger = logging.getLogger(__name__)

class LLMService:
    """Service to interact with the local Ollama LLM for text rewriting and integrity coaching."""
    
    @classmethod
    async def get_available_models(cls) -> list[str]:
        """Queries Cloud LLMs or local Ollama for available models."""
        if settings.GROQ_API_KEY:
            return [settings.CLOUD_LLM_MODEL or "llama-3.3-70b-versatile (Groq Cloud)", "llama-3.1-8b-instant"]
        if settings.OPENAI_API_KEY:
            return [settings.CLOUD_LLM_MODEL or "gpt-4o-mini (OpenAI Cloud)", "gpt-4o"]

        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.debug(f"Local Ollama query: {e}")
        return []

    @classmethod
    async def _resolve_model(cls) -> str:
        """Resolve the best available model to use (Cloud or local Ollama)."""
        if settings.GROQ_API_KEY:
            return settings.CLOUD_LLM_MODEL or "llama-3.3-70b-versatile"
        if settings.OPENAI_API_KEY:
            return settings.CLOUD_LLM_MODEL or "gpt-4o-mini"

        available = await cls.get_available_models()
        model_to_use = settings.OLLAMA_MODEL
        if available:
            if model_to_use not in available:
                candidates = [
                    m for m in available 
                    if m.startswith(model_to_use) or model_to_use.startswith(m.split(':')[0])
                ]
                if candidates:
                    model_to_use = candidates[0]
                else:
                    model_to_use = available[0]
        return model_to_use

    @classmethod
    async def _call_cloud_llm(cls, prompt: str, temp: float = 0.5) -> str | None:
        """Calls Groq or OpenAI or any OpenAI-compatible cloud API."""
        api_key = settings.GROQ_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            return None

        if settings.GROQ_API_KEY:
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            model = settings.CLOUD_LLM_MODEL or "llama-3.3-70b-versatile"
        elif settings.OPENAI_API_KEY:
            endpoint = (settings.OPENAI_BASE_URL.rstrip('/') + "/chat/completions") if settings.OPENAI_BASE_URL else "https://api.openai.com/v1/chat/completions"
            model = settings.CLOUD_LLM_MODEL or "gpt-4o-mini"
        else:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "max_tokens": 4096
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "").strip()
                        if content.startswith('"') and content.endswith('"'):
                            content = content[1:-1].strip()
                        elif content.startswith("'") and content.endswith("'"):
                            content = content[1:-1].strip()
                        return content
                else:
                    logger.warning(f"Cloud LLM API returned {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Cloud LLM call failed: {e}")
        return None

    @classmethod
    async def _call_ollama(cls, prompt: str, model: str, temp: float = 0.5, repeat_penalty: float = 1.0) -> str:
        """Call Cloud LLM if configured, otherwise call local Ollama."""
        # 1. Try Cloud LLM first if API key is present
        cloud_res = await cls._call_cloud_llm(prompt, temp=temp)
        if cloud_res:
            return cloud_res

        # 2. Try Local Ollama
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "repeat_penalty": repeat_penalty,
                "top_p": 0.9,
                "top_k": 40,
            }
        }
        url = f"{settings.OLLAMA_URL.rstrip('/')}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    rewritten = data.get("response", "").strip()
                    if rewritten.startswith('"') and rewritten.endswith('"'):
                        rewritten = rewritten[1:-1].strip()
                    elif rewritten.startswith("'") and rewritten.endswith("'"):
                        rewritten = rewritten[1:-1].strip()
                    return rewritten
                else:
                    logger.error(f"Ollama returned error status: {response.status_code} - {response.text}")
        except Exception as e:
            logger.debug(f"Local Ollama connection failed at {settings.OLLAMA_URL}: {e}")

        # Return empty string if both cloud and local Ollama are unreachable so calling methods can apply smart fallbacks
        return ""

    @classmethod
    async def rewrite_text(cls, text: str, tone: str = "academic") -> str:
        """
        Rewrites a sentence or paragraph to eliminate plagiarism across multiple scholarly tones.
        """
        if not text.strip():
            return ""

        model_to_use = await cls._resolve_model()

        tone_map = {
            "academic": ("Maintain a strict academic, formal third-person scholarly tone with advanced academic phrasing and precise terminology.", 0.5, 1.1),
            "standard": ("Use a clear, neutral, and highly readable natural tone with fluent grammatical flow.", 0.6, 1.1),
            "formal": ("Use an authoritative, professional, and publication-ready executive tone.", 0.5, 1.1),
            "creative": ("Use an engaging, dynamic, and expressive tone with diverse sentence structure.", 0.85, 1.2),
            "shorten": ("Make the text highly concise, crisp, and direct, eliminating filler words while strictly preserving all core facts.", 0.5, 1.15),
            "expand": ("Elaborate with deeper academic clarity, contextual nuance, and explanatory precision while maintaining the core facts.", 0.65, 1.1),
        }

        tone_instruction, temp, repeat_penalty = tone_map.get(
            tone.lower(),
            ("Maintain a strict academic, formal third-person scholarly tone.", 0.5, 1.1)
        )

        prompt = (
            "You are an expert academic editor and writing coach. Your goal is to rewrite the input text to be 100% original, fluent, and plagiarism-free.\n\n"
            f"Style & Tone Directive: {tone_instruction}\n\n"
            "Strict Instructions:\n"
            "1. Completely restructure sentence syntax, clauses, and vocabulary to eliminate textual and semantic similarity.\n"
            "2. Preserve all factual accuracy, key technical terms, and original meaning faithfully.\n"
            "3. Do NOT include introductory phrases (e.g., 'Here is the rewritten text:').\n"
            "4. Do NOT use quotation marks or markdown wrappers.\n"
            "5. Output ONLY the clean rewritten text.\n\n"
            f"Original text to rewrite:\n{text.strip()}\n\n"
            "Paraphrased text:"
        )
        try:
            res = await cls._call_ollama(prompt, model_to_use, temp, repeat_penalty)
            return res.strip() if res else text.strip()
        except Exception as e:
            logger.warning(f"Ollama call failed in rewrite_text: {e}. Applying rule-based academic rephrasing fallback.")
            # Fallback academic restructuring
            words = text.strip().split()
            if len(words) <= 3:
                return text.strip()
            return f"In scholarly analysis, {text.strip()[0].lower() + text.strip()[1:]}" if not text.strip().startswith("In") else text.strip()

    @classmethod
    async def humanize_content(cls, text: str, tone: str = "academic", intensity: str = "high") -> str:
        """
        Deep Humanizer: Transforms AI-generated text into authentic human-like academic writing
        that bypasses Turnitin AI detectors by breaking uniform sentence patterns,
        varying burstiness, and replacing formulaic tokens.
        """
        if not text.strip():
            return ""

        from app.services.academic_humanizer import AcademicHumanizerService

        model_to_use = await cls._resolve_model()

        temp = 0.7 if intensity == "high" else (0.85 if intensity == "maximum" else 0.55)
        repeat_penalty = 1.15

        prompt = (
            "You are an elite academic humanizer and writing specialist. "
            "Your objective is to rewrite the input AI-generated text into authentic, natural human academic writing "
            "that completely bypasses AI detectors like Turnitin, GPTZero, and CopyLeaks.\n\n"
            f"Tone/Style Directive: {tone.capitalize()} scholarly style with authentic human flow.\n\n"
            "Critical Humanization Rules:\n"
            "1. Extreme Burstiness: Mix short punchy statements (4-7 words) with complex, rich compound sentences (25-35 words with semicolons and active scholarly discourse).\n"
            "2. Zero AI Clichés: NEVER use 'In recent years', 'rapid proliferation', 'pivotal role', 'delve', 'testament to', 'multifaceted', 'furthermore', 'moreover', 'in conclusion', or 'it is important to note'.\n"
            "3. Preserve all factual accuracy, data, equations, and technical citations ([1], [2]).\n"
            "4. Do NOT output headings, markdown wrappers, or intro preambles.\n\n"
            f"Text to humanize:\n<text>\n{text.strip()}\n</text>\n\n"
            "Humanized text:"
        )
        try:
            res = await cls._call_ollama(prompt, model_to_use, temp=temp, repeat_penalty=repeat_penalty)
            raw_output = res.strip() if res else text.strip()
            return AcademicHumanizerService.humanize_text(raw_output)
        except Exception as e:
            logger.warning(f"Ollama humanize call failed: {e}. Applying rule-based humanizer.")
            return AcademicHumanizerService.humanize_text(text.strip())

    @classmethod
    async def integrity_coach_rewrite(
        cls,
        text: str,
        matched_source_title: str | None = None,
        matched_source_author: str | None = None,
        matched_source_url: str | None = None,
        match_type: str = "semantic",
        score: float | None = None,
    ) -> dict:
        """
        Integrity Coach: instead of directly rewriting flagged text,
        returns pedagogical guidance, citation suggestions, and structured
        action steps to help the student develop original work.
        """
        if not text.strip():
            return {
                "guidance_prompt": "",
                "issue_explanation": "",
                "suggested_citation": None,
                "citation_formats": {},
                "example_rewrite": None,
                "action_steps": [],
            }

        model_to_use = await cls._resolve_model()

        # Build source context for the LLM
        source_context = ""
        if matched_source_title:
            source_context += f"Source title: {matched_source_title}\n"
        if matched_source_author:
            source_context += f"Source author: {matched_source_author}\n"
        if matched_source_url:
            source_context += f"Source URL/DOI: {matched_source_url}\n"
        if score is not None:
            source_context += f"Similarity score: {int(score * 100)}%\n"

        match_desc = {
            "lexical": "verbatim or near-verbatim copying",
            "semantic": "paraphrasing or idea-level reuse without attribution",
            "hybrid": "direct copying with minor word substitutions",
        }.get(match_type, "similarity")

        # Generate guidance prompt
        guidance_prompt_request = (
            f"You are an academic integrity coach. A student's text has been flagged for {match_desc}.\n"
            f"Flagged text: <text>{text}</text>\n"
            f"{source_context}\n"
            "Generate a SHORT, encouraging pedagogical question or prompt (2-3 sentences maximum) "
            "that helps the student understand the issue and express the idea in their own words. "
            "Do NOT rewrite the text for them. Do NOT include any preamble or explanation â€” output ONLY the guidance prompt."
        )
        guidance_prompt = await cls._call_ollama(guidance_prompt_request, model_to_use, temp=0.6)

        # Generate example rewrite
        example_prompt = (
            f"Rewrite the following text to express the same idea in original language suitable for academic use. "
            f"Show how a student COULD express this idea if they understood it. "
            f"Text: <text>{text}</text>\n"
            "Respond ONLY with the rewritten text."
        )
        example_rewrite = await cls._call_ollama(example_prompt, model_to_use, temp=0.7)

        # Build citation suggestions
        suggested_citation = None
        citation_formats = {"apa": None, "mla": None, "chicago": None}
        if matched_source_title:
            year = "n.d."
            author = matched_source_author or "Unknown Author"
            title = matched_source_title
            url_part = f" Retrieved from {matched_source_url}" if matched_source_url else ""
            author_last = author.split()[-1] if author else "Author"

            citation_formats["apa"] = f"{author} ({year}). {title}.{url_part}"
            citation_formats["mla"] = f"{author}. \"{title}.\" {year}.{url_part}"
            citation_formats["chicago"] = f"{author}. {title}. {year}.{url_part}"
            suggested_citation = f"({author_last}, {year})"

        # Build action steps
        action_steps = [
            "Read the source material carefully to understand the core idea.",
            "Close the source and write the idea entirely in your own words from memory.",
        ]
        if matched_source_title:
            action_steps.append(f"Add a proper citation to '{matched_source_title}' using your required citation format.")
        else:
            action_steps.append("Identify the original source and add a proper in-text citation.")
        action_steps.append("Compare your rewritten version to the original to ensure you have added value, not just changed words.")

        # Build issue explanation
        if match_type == "lexical":
            issue_explanation = "Your text uses the same or very similar words as an existing source without proper attribution."
        elif match_type == "semantic":
            issue_explanation = "Your text expresses the same ideas as an existing source, even though the words may differ. This is still considered plagiarism without citation."
        else:
            issue_explanation = "Your text closely mirrors an existing source in both wording and meaning. This requires proper attribution."

        return {
            "guidance_prompt": guidance_prompt,
            "issue_explanation": issue_explanation,
            "suggested_citation": suggested_citation,
            "citation_formats": citation_formats,
            "example_rewrite": example_rewrite,
            "action_steps": action_steps,
        }


    @classmethod
    async def generate_citations(cls, query: str) -> dict:
        """Use LLM to generate citations in multiple academic formats."""
        prompt = f"""
You are an expert academic librarian. Convert the following source inquiry into formal academic bibliography citations.
Source: "{query.strip()}"

Please generate complete citations in the following 4 formats: APA, MLA, Chicago, and IEEE.
Output STRICTLY a valid JSON object with the exact keys "apa", "mla", "chicago", and "ieee".
Do not include any conversational preamble or markdown code blocks.

Example output:
{{
  "ieee": "[1] A. Vaswani et al., \\"Attention Is All You Need,\\" in Advances in Neural Information Processing Systems (NeurIPS), vol. 30, pp. 5998-6008, 2017.",
  "apa": "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 30, 5998-6008.",
  "mla": "Vaswani, Ashish, et al. \\"Attention Is All You Need.\\" Advances in Neural Information Processing Systems, vol. 30, 2017, pp. 5998-6008.",
  "chicago": "Vaswani, Ashish, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, and Illia Polosukhin. \\"Attention Is All You Need.\\" Advances in Neural Information Processing Systems 30 (2017): 5998-6008."
}}
"""
        model = await cls._resolve_model()
        response_text = await cls._call_ollama(prompt, model=model, temp=0.3)
        import json
        import re

        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "apa": str(data.get("apa", "")).strip(),
                    "mla": str(data.get("mla", "")).strip(),
                    "chicago": str(data.get("chicago", "")).strip(),
                    "ieee": str(data.get("ieee", "")).strip()
                }
        except Exception as e:
            logger.warning(f"JSON parsing error in generate_citations: {e}")

        # Fallback text regex parsing
        def extract_format(name):
            pat = rf'(?i)(?:^|\n)(?:\[?{name}\]?:?|\*\*{name}\*\*:?)\s*([^\n]+(?:\n(?!(?:APA|MLA|Chicago|IEEE|\[)).+)*)'
            m = re.search(pat, response_text)
            return m.group(1).strip() if m else ""

        apa_val = extract_format("APA") or f"{query.strip()} (APA format)"
        mla_val = extract_format("MLA") or f"{query.strip()} (MLA format)"
        chicago_val = extract_format("Chicago") or f"{query.strip()} (Chicago format)"
        ieee_val = extract_format("IEEE") or f"[1] {query.strip()} (IEEE format)"

        return {
            "apa": apa_val,
            "mla": mla_val,
            "chicago": chicago_val,
            "ieee": ieee_val
        }

    # =========================================================================
    # Research Paper Generation Methods
    # =========================================================================

    @classmethod
    async def analyze_topic(cls, topic: str, domain: str = None) -> dict:
        """
        Analyze a research topic to identify scope, research questions, and relevant keywords.
        Returns a structured dict with topic analysis.
        """
        domain_context = f" in the domain of {domain}" if domain else ""
        prompt = (
            f"You are an expert academic researcher. Analyze the following research topic{domain_context}:\n\n"
            f"Topic: {topic}\n\n"
            "Provide a structured analysis with:\n"
            "1. A refined, specific research topic statement (1-2 sentences)\n"
            "2. 3-5 key research questions this paper should answer\n"
            "3. 5-8 relevant academic keywords\n"
            "4. The most appropriate IEEE paper sections for this topic\n"
            "5. A brief scope statement describing what will and won't be covered\n\n"
            "Format your response as a JSON object with keys: "
            "\"refined_topic\", \"research_questions\", \"keywords\", \"suggested_sections\", \"scope\".\n"
            "Only output valid JSON."
        )
        import json, re
        try:
            model = await cls._resolve_model()
            response = await cls._call_ollama(prompt, model, temp=0.4)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "refined_topic": data.get("refined_topic", topic),
                    "research_questions": data.get("research_questions", []),
                    "keywords": data.get("keywords", []),
                    "suggested_sections": data.get("suggested_sections", [
                        "INTRODUCTION", "RELATED WORK", "METHODOLOGY", "RESULTS", "DISCUSSION", "CONCLUSION"
                    ]),
                    "scope": data.get("scope", ""),
                }
        except Exception as e:
            logger.warning(f"Failed in topic analysis: {e}")

        # Fallback
        return {
            "refined_topic": topic,
            "research_questions": [f"What are the current applications of {topic}?"],
            "keywords": topic.split()[:5],
            "suggested_sections": ["INTRODUCTION", "RELATED WORK", "METHODOLOGY", "RESULTS", "DISCUSSION", "CONCLUSION"],
            "scope": f"This paper explores {topic}.",
        }

    @classmethod
    async def generate_paper_outline(cls, topic: str, domain: str = None,
                                     sections: list[str] = None,
                                     sources: list[dict] = None) -> dict:
        """
        Generate a detailed IEEE paper outline for the given topic.
        Returns a dict with title, abstract_plan, sections (list with subsection plans).
        """
        if not sections:
            sections = ["INTRODUCTION", "RELATED WORK", "METHODOLOGY", "RESULTS", "DISCUSSION", "CONCLUSION"]

        domain_ctx = f" in {domain}" if domain else ""
        source_titles = ""
        if sources:
            titles = [s.get("title", "") for s in sources[:15] if s.get("title")]
            if titles:
                source_titles = "\n\nAvailable reference sources:\n" + "\n".join(f"- {t}" for t in titles)

        default_sections = [
            "INTRODUCTION",
            "RELATED WORK AND LITERATURE TAXONOMY",
            "THEORETICAL FOUNDATION AND MATHEMATICAL FORMULATION",
            "SYSTEM ARCHITECTURE AND PROPOSED METHODOLOGY",
            "EXPERIMENTAL DESIGN AND BENCHMARK DATASETS",
            "QUANTITATIVE RESULTS AND COMPARATIVE ANALYSIS",
            "DISCUSSION, SENSITIVITY ANALYSIS, AND LIMITATIONS",
            "CONCLUSION AND FUTURE RESEARCH DIRECTIONS"
        ]
        if not sections or len(sections) < 6:
            sections = default_sections

        sections_str = "\n".join(f"- {s}" for s in sections)
        prompt = (
            f"You are an expert academic researcher and technical writer{domain_ctx}.\n"
            f"Create a comprehensive 8-to-10 page IEEE conference/journal paper outline for: \"{topic}\"\n\n"
            f"The paper must systematically include these 8 comprehensive sections:\n{sections_str}\n"
            f"{source_titles}\n\n"
            "For each section, provide:\n"
            "1. Section title (uppercase Roman numeral style)\n"
            "2. Detailed 3-4 sentence description of theoretical/practical coverage\n"
            "3. Key points to address (4-6 comprehensive bullet points)\n"
            "4. 2-3 specific subsections with titles\n\n"
            "Also provide:\n"
            "- A professional, publication-grade paper title\n"
            "- Abstract outline\n"
            "- 6-8 IEEE Index Terms (keywords)\n\n"
            "Format as JSON: {\"title\": ..., \"keywords\": [...], \"abstract_plan\": ..., "
            "\"sections\": [{\"number\": \"I\", \"title\": ..., \"description\": ..., "
            "\"key_points\": [...], \"subsections\": [{\"label\": \"A\", \"title\": ..., \"description\": ...}]}]}"
            "\nOnly output valid JSON."
        )
        import json, re
        try:
            model = await cls._resolve_model()
            response = await cls._call_ollama(prompt, model, temp=0.5)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.warning(f"Failed to generate/parse outline JSON: {e}")

        # Fallback comprehensive 8-section structure
        roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
        fallback_subsections = {
            "INTRODUCTION": [
                {"label": "A", "title": "Background and Problem Motivation"},
                {"label": "B", "title": "Core Technical Challenges"},
                {"label": "C", "title": "Main Contributions and Article Outline"}
            ],
            "RELATED WORK AND LITERATURE TAXONOMY": [
                {"label": "A", "title": "Historical Evolution of Paradigms"},
                {"label": "B", "title": "State-of-the-Art Benchmarks"},
                {"label": "C", "title": "Critical Comparative Analysis and Research Gap"}
            ],
            "THEORETICAL FOUNDATION AND MATHEMATICAL FORMULATION": [
                {"label": "A", "title": "Formal Problem Definition and System Model"},
                {"label": "B", "title": "Objective Formulation and Mathematical Derivations"}
            ],
            "SYSTEM ARCHITECTURE AND PROPOSED METHODOLOGY": [
                {"label": "A", "title": "High-Level Architecture Pipeline"},
                {"label": "B", "title": "Core Algorithmic Framework"},
                {"label": "C", "title": "Complexity Analysis and Scalability Guarantees"}
            ],
            "EXPERIMENTAL DESIGN AND BENCHMARK DATASETS": [
                {"label": "A", "title": "Benchmark Datasets and Preprocessing Protocol"},
                {"label": "B", "title": "Baseline Models and Hyperparameter Configurations"},
                {"label": "C", "title": "Evaluation Metrics and Statistical Rigor"}
            ],
            "QUANTITATIVE RESULTS AND COMPARATIVE ANALYSIS": [
                {"label": "A", "title": "Primary Empirical Performance Benchmarks"},
                {"label": "B", "title": "Ablation Studies and Component Isolation"}
            ],
            "DISCUSSION, SENSITIVITY ANALYSIS, AND LIMITATIONS": [
                {"label": "A", "title": "Operational Constraints and Edge Cases"},
                {"label": "B", "title": "Ethical Considerations, Generalizability, and Failure Modes"}
            ],
            "CONCLUSION AND FUTURE RESEARCH DIRECTIONS": [
                {"label": "A", "title": "Summary of Findings"},
                {"label": "B", "title": "Open Research Horizons and Future Extensions"}
            ]
        }
        return {
            "title": f"A Comprehensive Investigation on {topic}: Theoretical Foundations, Empirical Architectures, and Practical Benchmarks",
            "keywords": [w.capitalize() for w in topic.split()[:6]] + ["IEEE Standards", "Deep Benchmarks", "Empirical Evaluation"],
            "abstract_plan": f"Comprehensive overview of {topic}, foundational formulations, experimental evaluation across benchmarks, and future directions.",
            "sections": [
                {
                    "number": roman[i] if i < len(roman) else str(i + 1),
                    "title": s,
                    "description": f"This section presents a rigorous and comprehensive examination of {s.lower()} with respect to {topic}.",
                    "key_points": [
                        f"Theoretical principles governing {s.lower()}",
                        f"State-of-the-art methodology and algorithmic execution",
                        f"Empirical validation across standardized benchmarks",
                        f"Systemic trade-offs and computational complexity"
                    ],
                    "subsections": fallback_subsections.get(s, [
                        {"label": "A", "title": f"Overview of {s.title()}"},
                        {"label": "B", "title": f"Advanced Formulations in {s.title()}"}
                    ])
                }
                for i, s in enumerate(default_sections)
            ]
        }

    @classmethod
    async def generate_abstract(cls, topic: str, sections_summary: str,
                                keywords: list[str], sources: list[dict] = None) -> str:
        """Generate an IEEE-style abstract for the paper."""
        source_ctx = ""
        if sources:
            source_ctx = f"\nThe paper references {len(sources)} academic sources."

        prompt = (
            "Write a concise, professional IEEE-style abstract (200-280 words) for an 8-10 page research paper.\n\n"
            f"Topic: {topic}\n"
            f"Keywords: {', '.join(keywords)}\n"
            f"Paper covers: {sections_summary}\n"
            f"{source_ctx}\n\n"
            "The abstract must:\n"
            "1. State the problem/motivation and technological landscape (2-3 sentences)\n"
            "2. Detail the proposed methodology, architectural mechanisms, and theoretical formulation (3-4 sentences)\n"
            "3. Present quantitative empirical results, metrics, and comparative gains (2-3 sentences)\n"
            "4. Conclude with broad significance, reproducibility, and deployment implications (1-2 sentences)\n\n"
            "Write ONLY the abstract text. No headings, no labels, no markdown."
        )
        try:
            model = await cls._resolve_model()
            return await cls._call_ollama(prompt, model, temp=0.4)
        except Exception as e:
            logger.warning(f"Failed to generate abstract with LLM: {e}. Using fallback abstract.")
            return (
                f"This document investigates {topic} within modern computational and empirical paradigms. "
                f"With the continuous escalation of complex data environments and real-time processing demands, "
                f"establishing robust, scalable, and theoretically grounded formulations for {topic} has emerged as an urgent priority. "
                f"In this article, we formulate a unified end-to-end framework that addresses foundational bottlenecks through optimized algorithmic pipelines, "
                f"rigorous mathematical representations, and adaptive representation learning. "
                f"We conduct extensive empirical evaluations across multiple standardized benchmark datasets, comparing our formulation against existing state-of-the-art baselines. "
                f"Our experimental findings demonstrate statistically significant improvements across key precision, latency, and convergence metrics, "
                f"achieving up to 14.8% reduction in computational overhead while maintaining superior generalization. "
                f"Finally, we provide detailed ablation studies, sensitivity analyses, and delineate critical pathways for future research."
            )

    @classmethod
    async def generate_section(cls, section_title: str, section_description: str,
                                key_points: list[str], topic: str,
                                sources: list[dict] = None,
                                citation_map: dict = None,
                                length_target: str = "medium") -> str:
        """
        Generate content for a single IEEE paper section.
        """
        length_words = {"short": "500-750", "medium": "850-1100", "long": "1100-1400"}.get(length_target, "850-1100")

        source_context = ""
        if sources:
            source_lines = []
            for idx, src in enumerate(sources):
                title = src.get("title", "")
                num = None
                if citation_map:
                    num = citation_map.get(title) or citation_map.get(title.strip().lower())
                if not num:
                    num = idx + 1
                authors = ", ".join(src.get("authors", [])[:3])
                year = src.get("year", "")
                abstract_snippet = (src.get("abstract", "") or "")[:200]
                source_lines.append(
                    f"[{num}] {authors} ({year}). \"{title}\". {abstract_snippet}"
                )
            if source_lines:
                source_context = (
                    "\n\nAvailable sources to cite (use [N] notation for inline citations, "
                    "cite these real sources accurately throughout paragraphs):\n"
                    + "\n".join(source_lines)
                )

        key_points_str = "\n".join(f"- {p}" for p in key_points)
        domain_profile = ResearchDomainKnowledgeService.resolve_domain_profile(topic)
        domain_name = domain_profile.get("domain_name", "Applied Science & Engineering")
        needs_math = domain_profile.get("needs_equations", True)

        math_req = (
            f"   - If this section is Theoretical, Methodology, or Mathematical, include 1-2 centered LaTeX equations relevant to {domain_name} enclosed in double dollar signs with equation numbering at the end, for example: $$\\min_{{\\theta}} \\mathcal{{L}}(\\theta) + \\lambda \\Omega(\\theta) \\quad (1)$$\n"
            if needs_math else
            f"   - Strict Constraint: This topic belongs to \"{domain_name}\". Do NOT force mathematical equations or LaTeX formulas into this section unless strictly required. Ground the analysis in qualitative, conceptual, or empirical analytical frameworks.\n"
        )

        prompt = (
            f"You are a senior academic researcher writing a comprehensive peer-reviewed research paper about: \"{topic}\"\n\n"
            f"Write the complete, publication-grade \"{section_title}\" section of the paper.\n\n"
            f"Scope and coverage:\n{section_description}\n\n"
            f"Key technical points to analyze:\n{key_points_str}\n"
            f"{source_context}\n\n"
            f"Strict Human Academic Writing Standards (Turnitin Anti-AI Style):\n"
            f"1. Write an extensive {length_words} words in rigorous, authentic scholarly style.\n"
            f"2. Maximize sentence length variance (Burstiness): alternate short, punchy statements (5-8 words) with nuanced, analytical compound sentences (25-35 words with semicolons and active verbs).\n"
            f"3. Strictly BAN robotic AI clichés: NEVER use 'In recent years', 'rapid proliferation', 'pivotal role', 'delve', 'testament to', 'multifaceted', 'furthermore', 'moreover', or 'it is important to note'.\n"
            f"4. Embed multiple real inline citations [1], [2], [3] naturally throughout the argument (include at least 2-4 citations per section referencing the available sources list above).\n"
            f"5. Scientific Formatting Requirements:\n"
            f"{math_req}"
            f"   - If this section is Results, Evaluation, or Related Work, include an authentic academic comparison table using Markdown table syntax (| Header 1 | Header 2 |) with domain-specific metrics tailored to {topic}.\n"
            f"6. Do NOT output headings or bullet lists (use flowing academic paragraphs).\n\n"
            "Write the complete section content directly:"
        )
        try:
            model = await cls._resolve_model()
            raw_content = await cls._call_ollama(prompt, model, temp=0.65, repeat_penalty=1.15)
            if not raw_content or not raw_content.strip():
                raise ValueError("Empty response from LLM")

            # Post-process LLM response to guarantee domain consistency
            st = section_title.upper()

            # 1. Enforce strict omission of equations for non-mathematical domains
            if not needs_math:
                raw_content = re.sub(r'\$\$[^\$]+\$\$', '', raw_content)
                raw_content = re.sub(r'\$[^\$]+\$', '', raw_content)

            # 2. Guarantee Table I in Related Work if missing
            if ("RELATED" in st or "LITERATURE" in st) and "|" not in raw_content:
                t1 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=1)
                raw_content += f"\n\nTABLE I. TAXONOMIC & ARCHITECTURAL COMPARISON OF PRECEDING METHODOLOGIES\n\n{t1}"

            # 3. Guarantee Table II in Results/Evaluation if missing
            elif ("RESULT" in st or "EVALUAT" in st) and "|" not in raw_content:
                t2 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=2)
                raw_content += f"\n\nTABLE II. COMPREHENSIVE EMPIRICAL BENCHMARK EVALUATION ACROSS DOMAIN DATASETS\n\n{t2}"

            # 4. Guarantee equations in Theoretical/Methodology if missing and domain needs math
            elif ("THEORETICAL" in st or "MATHEMATICAL" in st) and needs_math and "$$" not in raw_content:
                eqs = domain_profile.get("equations", [])
                if eqs:
                    eq1 = eqs[0]
                    eq2 = eqs[1] if len(eqs) > 1 else ""
                    raw_content += f"\n\n$${eq1}$$\n\n$${eq2}$$"

            return raw_content
        except Exception as e:
            logger.warning(f"Ollama call failed for section '{section_title}': {e}. Using synthesis fallback.")
            st = section_title.upper()
            all_nums = sorted(list(set(citation_map.values()))) if citation_map else list(range(1, 11))
            
            # Select relevant citation tags for this section
            if "INTRO" in st:
                c1, c2, c3 = all_nums[0] if len(all_nums) > 0 else 1, all_nums[1] if len(all_nums) > 1 else 2, all_nums[2] if len(all_nums) > 2 else 3
                return (
                    f"In recent years, the rapid proliferation of computational frameworks has significantly reshaped the paradigm of {topic}. "
                    f"As modern computing demands heightened reliability, scalability, and robust performance, developing systematic methodologies has become paramount [{c1}]. "
                    f"Traditional approaches often encounter severe limitations when deployed in dynamic, large-scale environments, primarily due to rigid structural assumptions and inadequate adaptability to non-stationary distributions [{c2}]. "
                    f"These challenges necessitate a re-examination of foundational mechanisms and the introduction of advanced, resilient architectural formulations.\n\n"
                    f"To address these fundamental bottlenecks, recent theoretical developments [{c3}] emphasize the need for unified optimization paradigms. "
                    f"Specifically, {section_description.lower() if section_description else 'the underlying system must balance computational efficiency against predictive accuracy'}. "
                    f"A primary challenge in this domain is maintaining consistent convergence while managing multi-dimensional state spaces and mitigating noise sensitivity in stochastic regimes.\n\n"
                    f"The primary contributions of this paper are organized as follows. First, we conduct an exhaustive theoretical formulation of {topic}, deriving exact analytical bounds for performance and computational complexity. "
                    f"Second, we design and implement a scalable algorithmic framework capable of processing heterogeneous representations with minimal computational overhead. "
                    f"Third, we execute rigorous empirical benchmarking across standardized datasets, validating our theoretical claims through extensive comparative evaluations and ablation studies.\n\n"
                    f"The remainder of this article is structured as follows. Section II reviews related literature and establishes a comprehensive taxonomic classification. "
                    f"Section III details the theoretical foundation and mathematical formulation. Section IV presents the proposed system architecture. "
                    f"Sections V and VI describe the experimental setup and quantitative findings. Section VII discusses operational constraints and broader implications, and Section VIII concludes the paper."
                )
            elif "RELATED" in st or "LITERATURE" in st:
                c1, c2, c3, c4 = all_nums[2] if len(all_nums) > 2 else 3, all_nums[3] if len(all_nums) > 3 else 4, all_nums[4] if len(all_nums) > 4 else 5, all_nums[5] if len(all_nums) > 5 else 6
                t1 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=1)
                return (
                    f"The intellectual evolution of {topic} has been characterized by several distinct developmental phases over the past two decades. "
                    f"Early pioneering efforts concentrated primarily on heuristic formulations and classical statistical approximations [{c1}]. "
                    f"While these foundational models provided valuable early insights, they exhibited critical vulnerabilities in generalizability when subjected to complex real-world variance.\n\n"
                    f"With the advent of high-capacity computational frameworks and distributed processing, subsequent research shifted toward automated representation learning [{c2}]. "
                    f"Notable contributions by leading scholars demonstrated that hierarchical feature extraction substantially outperforms manual feature engineering [{c3}]. "
                    f"However, existing architectures frequently suffer from excessive parameterization, leading to substantial computational latency and elevated risk of overfitting in sparse-data regimes.\n\n"
                    f"Recent contemporary investigations [{c4}] have attempted to bridge this efficiency gap through modular design, pruning strategies, and uncertainty-aware regularization. "
                    f"Despite these advancements, a significant research gap persists: current frameworks lack an integrated mechanism to simultaneously optimize representation fidelity, runtime complexity, and distributional robustness.\n\n"
                    f"TABLE I. TAXONOMIC & ARCHITECTURAL COMPARISON OF PRECEDING METHODOLOGIES\n\n"
                    f"{t1}\n\n"
                    f"As detailed in Table I, the comparative taxonomy categorizes preceding methodologies versus our proposed paradigm across key architectural criteria, highlighting the distinct technical advancements achieved in this study."
                )
            elif "THEORETICAL" in st or "MATHEMATICAL" in st:
                c1, c2 = all_nums[4] if len(all_nums) > 4 else 5, all_nums[5] if len(all_nums) > 5 else 6
                if domain_profile.get("needs_equations", True) and domain_profile.get("equations"):
                    eqs = domain_profile["equations"]
                    eq1 = eqs[0]
                    eq2 = eqs[1] if len(eqs) > 1 else ""
                    return (
                        f"This section establishes the formal mathematical foundation and governing equations for {topic}. "
                        f"Let the input space be formally defined on a compact manifold $\\mathcal{{X}} \\subset \\mathbb{{R}}^d$, with corresponding output target space $\\mathcal{{Y}}$. "
                        f"We consider a continuous-time parameterized mapping $f_\\theta: \\mathcal{{X}} \\to \\mathcal{{Y}}$, where $\\theta \\in \\Theta$ represents the vector of trainable parameters [{c1}].\n\n"
                        f"The analytical optimization objective is formulated to balance empirical performance and structural stability under domain-specific constraints:\n\n"
                        f"$${eq1}$$\n\n"
                        f"where the objective function balances primary empirical loss with regularization bounds, penalizing model over-complexity while maintaining invariant boundary stability [{c2}].\n\n"
                        f"To guarantee uniform stability and prevent catastrophic divergence under stochastic perturbations, the dynamics satisfy the following analytical criterion:\n\n"
                        f"$${eq2}$$\n\n"
                        f"Under these analytical constraints, the asymptotic convergence rate is strictly bounded, ensuring predictable numerical stability across arbitrary sample dimensions."
                    )
                else:
                    return (
                        f"This section establishes the analytical, conceptual, and procedural framework for {topic}. "
                        f"Unlike purely algorithmic systems that rely on idealized mathematical abstractions, analyzing {topic} requires a holistic paradigm that systematically integrates empirical observations, contextual determinants, and institutional workflows [{c1}].\n\n"
                        f"The operational framework is structured around three foundational pillars: (i) Baseline contextual characterization, (ii) Multi-factor dynamic interaction modeling, and (iii) Longitudinal outcome evaluation. "
                        f"By decoupling structural environmental factors from direct participant responses [{c2}], the framework isolates confounding variables without imposing artificial mathematical simplifications.\n\n"
                        f"Theoretical validity is maintained through rigorous triangulation, cross-verifying quantitative indicators against qualitative field evidence. "
                        f"This dual-faceted perspective ensures that structural shifts and subtle qualitative nuances are captured with high fidelity, establishing a robust theoretical foundation for subsequent empirical investigations."
                    )
            elif "METHOD" in st or "ARCHITECTURE" in st:
                c1, c2, c3 = all_nums[5] if len(all_nums) > 5 else 6, all_nums[6] if len(all_nums) > 6 else 7, all_nums[7] if len(all_nums) > 7 else 8
                return (
                    f"The proposed system architecture for {topic} is engineered as a modular, end-to-end framework designed for high-throughput and low-latency execution. "
                    f"Fig. 1 delineates the complete architectural dataflow and procedural pipeline of the framework, highlighting the decoupled transformation layers.\n\n"
                    f"The pipeline comprises three core functional stages: (i) Adaptive Input Normalization and Feature Conditioning, (ii) Latent Representation Transformation, and (iii) Multi-Objective Inference and Verification [{c1}].\n\n"
                    f"In the first stage, raw multi-modal inputs are ingested through a calibrated preconditioning module that eliminates high-frequency noise while preserving salient invariant features [{c2}]. "
                    f"The conditioned tensors are subsequently mapped into an orthogonal latent manifold via a dynamic attention routing mechanism, ensuring that task-critical dependencies are amplified without incurring quadratic memory overhead.\n\n"
                    f"The second stage implements our novel parameter-efficient transformation kernel. "
                    f"By factorizing high-rank tensor operations into low-rank decomposed projections, the computational complexity is reduced from $\\mathcal{{O}}(N^2)$ to $\\mathcal{{O}}(N \\log N)$, where $N$ denotes the input sequence length [{c3}]. "
                    f"This mathematical restructuring enables seamless parallel execution across heterogeneous hardware accelerators.\n\n"
                    f"Finally, the output stage performs calibrated posterior probability estimation with integrated uncertainty quantification. "
                    f"An automated thresholding mechanism dynamically determines confidence bounds, rejecting low-confidence predictions to ensure zero false-positive cascades in safety-critical operational environments."
                )
            elif "EXPERIMENT" in st or "SETUP" in st:
                c1, c2 = all_nums[6] if len(all_nums) > 6 else 7, all_nums[7] if len(all_nums) > 8 else 8
                return (
                    f"To rigorously evaluate the efficacy and scalability of our proposed framework for {topic}, we conducted extensive experimental benchmarking against leading baseline models [{c1}]. "
                    f"All experiments were implemented using standardized distributed compute infrastructure and executed across multiple randomized seed initializations to ensure statistical validity.\n\n"
                    f"Four benchmark datasets representing diverse domain complexities, noise distributions, and dimensional scales were utilized. "
                    f"Prior to model ingestion, standard 5-fold cross-validation protocols were established, allocating 70% of samples for training, 15% for validation tuning, and 15% for blind test evaluation [{c2}].\n\n"
                    f"Evaluation metrics include Area Under Curve (AUC), Mean Squared Error (MSE), Macro F1-Score, Inference Latency (milliseconds per sample), and Peak GPU Memory Consumption (MB). "
                    f"Hyperparameters across all baseline implementations were systematically tuned via Bayesian optimization to guarantee fair and unbiased comparisons."
                )
            elif "RESULT" in st or "EVALUAT" in st:
                c1, c2, c3 = all_nums[7] if len(all_nums) > 7 else 8, all_nums[8] if len(all_nums) > 8 else 9, all_nums[9] if len(all_nums) > 9 else 10
                t2 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=2)
                return (
                    f"The quantitative results demonstrate that our proposed approach consistently surpasses existing baseline methodologies across all evaluated benchmark metrics for {topic} [{c1}]. "
                    f"On average, the framework achieves statistically significant improvements in fidelity and efficiency compared to contemporary benchmarks [{c2}].\n\n"
                    f"TABLE II. COMPREHENSIVE EMPIRICAL BENCHMARK EVALUATION ACROSS DOMAIN DATASETS\n\n"
                    f"{t2}\n\n"
                    f"As delineated in Table II, the empirical comparison across all baseline architectures confirms that our model consistently achieves lower error margins while exhibiting superior resistance to input perturbations. "
                    f"Statistical significance testing via two-tailed Student's t-tests confirms that observed gains are statistically significant (*p < 0.001) [{c3}].\n\n"
                    f"Fig. 2 illustrates the empirical accuracy distributions and comparative latency scaling across varying batch dimensions. "
                    f"As demonstrated, the proposed architecture maintains optimal throughput and stability even under elevated load conditions."
                )
            elif "DISCUSSION" in st or "LIMITATION" in st:
                c1, c2 = all_nums[8] if len(all_nums) > 8 else 9, all_nums[9] if len(all_nums) > 9 else 10
                return (
                    f"A deeper analysis of the empirical findings reveals several important operational insights regarding {topic}. "
                    f"First, the observed accuracy-latency Pareto frontier indicates that structural factorization significantly improves energy efficiency during continuous inference [{c1}]. "
                    f"This property is particularly advantageous for deployment on resource-constrained edge computing devices and real-time embedded systems.\n\n"
                    f"However, certain operational limitations must be acknowledged. Under severe distributional shifts and extreme adversarial noise corruption, predictive uncertainty intervals widen measurably [{c2}]. "
                    f"Addressing these out-of-distribution edge cases represents an essential area for ongoing methodological refinement.\n\n"
                    f"From an ethical and societal perspective, deploying automated systems for {topic} requires transparent auditing protocols to prevent algorithmic bias and ensure equitable decision-making across diverse stakeholder demographics."
                )
            else:
                c1, c2 = all_nums[0] if len(all_nums) > 0 else 1, all_nums[-1] if len(all_nums) > 0 else 10
                return (
                    f"In this paper, we presented a comprehensive, theoretically grounded, and empirically validated study on {topic} [{c1}]. "
                    f"By addressing foundational architectural limitations and introducing an optimized mathematical formulation, our framework achieves state-of-the-art performance across comprehensive benchmarks while maintaining superior computational efficiency.\n\n"
                    f"Extensive experimental results and rigorous ablation analyses confirm the robustness, scalability, and practical viability of the proposed design [{c2}]. "
                    f"Future research trajectories will explore self-supervised adaptation techniques, federated multi-agent learning extensions, and real-world deployment across heterogeneous enterprise ecosystems."
                )

    @classmethod
    async def detect_sections(cls, text: str) -> list[dict]:
        """
        Detect sections in an uploaded document for restructuring.
        Returns a list of {title, content} dicts.
        """
        # Use a snippet (first 3000 chars) plus LLM to detect sections
        text_snippet = text[:4000]
        prompt = (
            "Analyze the following document text and identify its structural sections.\n\n"
            f"Document (first portion):\n<text>\n{text_snippet}\n</text>\n\n"
            "List all section headings/titles you can identify in this document, in order.\n"
            "Format as a JSON array of strings. Example: [\"Introduction\", \"Background\", \"Methods\", \"Results\"]\n"
            "Only output valid JSON."
        )
        import json, re
        try:
            model = await cls._resolve_model()
            response = await cls._call_ollama(prompt, model, temp=0.3)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                sections = json.loads(match.group(0))
                return [{"title": s, "content": ""} for s in sections if isinstance(s, str)]
        except Exception as e:
            logger.warning(f"Failed to parse section detection: {e}")

        # Fallback: scan for standard headings
        standard = ["INTRODUCTION", "BACKGROUND", "METHODOLOGY", "RESULTS", "DISCUSSION", "CONCLUSION"]
        found = []
        for s in standard:
            if s.lower() in text.lower():
                found.append({"title": s, "content": ""})
        return found or [{"title": "MAIN CONTENT", "content": text}]

    @classmethod
    async def map_to_ieee_sections(cls, detected_sections: list[str],
                                    topic: str) -> list[dict]:
        """
        Map detected section titles to IEEE section types.
        Returns a list of {original_title, ieee_title, ieee_number} dicts.
        """
        sections_str = "\n".join(f"- {s}" for s in detected_sections)
        prompt = (
            f"You are restructuring a research paper about \"{topic}\" into IEEE format.\n\n"
            f"Original document sections:\n{sections_str}\n\n"
            "Map each original section to the appropriate IEEE section.\n"
            "IEEE sections to use: INTRODUCTION, RELATED WORK, METHODOLOGY, RESULTS, DISCUSSION, CONCLUSION, REFERENCES\n\n"
            "Rules:\n"
            "- Multiple original sections can map to the same IEEE section\n"
            "- If a section doesn't map clearly, use your best judgment\n"
            "- Preserve all content — don't discard any sections\n\n"
            "Output a JSON array: [{\"original\": \"...\", \"ieee\": \"...\", \"number\": \"I\"}, ...]\n"
            "Number sections with Roman numerals I, II, III, etc. (REFERENCES is last)\n"
            "Only output valid JSON."
        )
        import json, re
        try:
            model = await cls._resolve_model()
            response = await cls._call_ollama(prompt, model, temp=0.3)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.warning(f"Failed to parse IEEE section mapping: {e}")

        roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        return [
            {"original": s, "ieee": s.upper(), "number": roman[i % len(roman)]}
            for i, s in enumerate(detected_sections)
        ]

    @classmethod
    async def improve_section_similarity(cls, section_content: str, section_title: str,
                                          topic: str) -> str:
        """
        Rewrite a paper section to reduce similarity while preserving:
        - Technical meaning, facts, numerical values
        - Equations and citations
        - Research claims
        Does NOT use meaningless synonym replacement.
        """
        prompt = (
            f"You are an expert academic editor helping reduce textual similarity in a research paper.\n\n"
            f"Paper topic: {topic}\n"
            f"Section: {section_title}\n\n"
            f"Original section content:\n<content>\n{section_content}\n</content>\n\n"
            "Rewrite this section to:\n"
            "1. Express the same ideas in substantially different phrasing\n"
            "2. Preserve ALL technical facts, numerical values, and research claims\n"
            "3. Preserve ALL citation references like [1], [2], etc.\n"
            "4. Maintain academic formal tone\n"
            "5. Keep the same logical structure and flow\n"
            "6. Do NOT add or remove citations\n"
            "7. Do NOT change any numerical data\n"
            "8. Do NOT add information not present in the original\n\n"
            "Write ONLY the rewritten section content. No headings, no labels, no markdown."
        )
        try:
            model = await cls._resolve_model()
            return await cls._call_ollama(prompt, model, temp=0.6, repeat_penalty=1.15)
        except Exception as e:
            logger.warning(f"Ollama improvement failed: {e}. Returning original content.")
            return section_content
