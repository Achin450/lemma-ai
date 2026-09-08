"""
Tests for Domain Knowledge Synthesizer, Dynamic Equations, and Topic-Specific Tables.
"""
import pytest
import asyncio
from app.services.research_domain_knowledge import ResearchDomainKnowledgeService
from app.services.academic_humanizer import AcademicHumanizerService
from app.services.llm import LLMService

def test_qualitative_domains_have_no_equations():
    """Topics in qualitative social sciences, ethics, and education must not have forced equations."""
    topics = [
        "Qualitative Analysis of AI Ethics in Higher Education",
        "Policy Governance and Pedagogical Challenges in Digital Classrooms",
        "A Sociological Survey on Remote Learning Equity"
    ]
    for topic in topics:
        profile = ResearchDomainKnowledgeService.resolve_domain_profile(topic)
        assert profile["needs_equations"] is False, f"Expected needs_equations=False for topic '{topic}'"
        assert len(ResearchDomainKnowledgeService.get_topic_equations(topic)) == 0

def test_clinical_healthcare_domains_have_no_forced_equations():
    """Clinical healthcare and patient trial topics must not have forced equations."""
    topics = [
        "Clinical Decision Support for Oncology Patient Triage",
        "Hospital Healthcare Outcomes in ICU Patient Management"
    ]
    for topic in topics:
        profile = ResearchDomainKnowledgeService.resolve_domain_profile(topic)
        assert profile["needs_equations"] is False, f"Expected needs_equations=False for clinical topic '{topic}'"
        assert len(ResearchDomainKnowledgeService.get_topic_equations(topic)) == 0

def test_mathematical_domains_have_tailored_equations():
    """Engineering, vision, robotics, and crypto must have specific tailored equations."""
    # Robotics
    p_robotics = ResearchDomainKnowledgeService.resolve_domain_profile("Autonomous Drone Trajectory Planning and Obstacle Avoidance")
    assert p_robotics["needs_equations"] is True
    eqs = ResearchDomainKnowledgeService.get_topic_equations("Autonomous Drone Trajectory Planning")
    assert len(eqs) >= 1
    assert "\\dot{\\mathbf{x}}" in eqs[0] or "J(\\mathbf{u})" in eqs[1]

    # Computer Vision
    p_cv = ResearchDomainKnowledgeService.resolve_domain_profile("Real-Time Object Detection and Instance Segmentation using YOLO")
    assert p_cv["needs_equations"] is True
    eqs_cv = ResearchDomainKnowledgeService.get_topic_equations("Real-Time Object Detection and Instance Segmentation")
    assert "\\mathcal{L}_{\\text{total}}" in eqs_cv[0] or "GIoU" in eqs_cv[0]

    # Security
    p_sec = ResearchDomainKnowledgeService.resolve_domain_profile("Zero-Knowledge Proofs in Blockchain Smart Contract Security")
    assert p_sec["needs_equations"] is True
    eqs_sec = ResearchDomainKnowledgeService.get_topic_equations("Zero-Knowledge Proofs in Blockchain")
    assert "\\text{Proof}_{\\text{ZK}}" in eqs_sec[0] or "Entropy" in eqs_sec[1]

def test_domain_specific_tables_generated():
    """Checks that domain knowledge generates distinct Table I and Table II."""
    topic = "Deep Learning for Medical Image Segmentation"
    t1 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=1)
    t2 = ResearchDomainKnowledgeService.generate_topic_markdown_table(topic, table_num=2)

    assert "|" in t1
    assert "Backbone" in t1 or "Architecture" in t1
    assert "|" in t2
    assert "mAP" in t2 or "Recall" in t2 or "IoU" in t2

def test_academic_humanizer_preserves_markdown_tables():
    """Ensure AcademicHumanizerService does NOT strip newlines from markdown tables."""
    table_text = (
        "In the subsequent trial, empirical results were evaluated.\n\n"
        "TABLE I. QUANTITATIVE BENCHMARK EVALUATION\n\n"
        "| Architecture | Accuracy (%) | Latency (ms) |\n"
        "| :--- | :--- | :--- |\n"
        "| Baseline Model | 82.4% | 42.1 ms |\n"
        "| Proposed System (Ours) | 97.8% | 14.5 ms |\n\n"
        "These results demonstrate statistically significant improvements across all metrics."
    )
    humanized = AcademicHumanizerService.humanize_text(table_text)
    assert "| Baseline Model | 82.4% | 42.1 ms |" in humanized
    assert "| Proposed System (Ours) | 97.8% | 14.5 ms |" in humanized
    # Table rows must remain on separate lines
    lines = [l.strip() for l in humanized.split("\n") if l.strip().startswith("|")]
    assert len(lines) == 4, f"Expected 4 table lines, got {len(lines)}"

def test_llm_fallback_selective_equations_and_tables():
    """Test LLM fallback generates topic-specific tables and selectively omits equations."""
    async def _run():
        # 1. Non-mathematical topic: Must NOT have \min_\theta equation
        content_qual = await LLMService.generate_section(
            section_title="THEORETICAL FRAMEWORK",
            section_description="Conceptual formulation of educational ethics.",
            key_points=["Pedagogical integrity", "Institutional equity"],
            topic="Qualitative Study on AI Ethics in Higher Education"
        )
        assert "\\min_{\\theta" not in content_qual
        assert "Lipschitz" not in content_qual
        assert any(w in content_qual.lower() for w in ["framework", "pedagogical", "ethical", "conceptual", "analytical", "operational"])

        # 2. Results section: Must contain dynamic Markdown table
        content_results = await LLMService.generate_section(
            section_title="EXPERIMENTAL RESULTS AND EVALUATION",
            section_description="Empirical benchmark across datasets.",
            key_points=["Model accuracy", "Inference latency"],
            topic="Autonomous Robot Trajectory Control with MPC"
        )
        assert "|" in content_results
        assert "table" in content_results.lower() or "TABLE" in content_results
        assert any(m in content_results.lower() for m in ["rmse", "latency", "tracking", "proposed", "error"])

    asyncio.run(_run())
