"""
End-to-end and unit tests for Lemma AI Research Paper Assistant workflows:
1. Generate Research Paper (Workflow A)
2. Restructure to IEEE (Workflow B)
3. Plagiarism / Similarity Check (Workflow C)
4. Citation Manager and Source-Awareness
5. IEEE Formatter & Exporter (PDF + DOCX)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas.research import (
    ResearchPaper, PaperSection, PaperSubsection, Citation, SourceRecord,
    GenerateRequest, PaperLength, PaperType, PaperStatus, SimilarityReport
)
from app.services.citation_manager import CitationManager
from app.services.ieee_formatter import IEEEFormatterService
from app.services.export_service import ExportService
from app.services.paper_store import PaperStore
from app.services.paper_restructurer import PaperRestructurerService
from app.services.research_generator import ResearchGeneratorService


# ===========================================================================
# 1. Citation Manager Tests (Source-Awareness, Numbering, Consistency)
# ===========================================================================

def test_citation_manager_source_registration_and_numbering():
    """Verify CitationManager assigns sequential 1-indexed numbers and reuses them."""
    cm = CitationManager()

    src1 = SourceRecord(
        title="Deep Residual Learning for Image Recognition",
        authors=["Kaiming He", "Xiangyu Zhang"],
        year="2016",
        source="CVPR",
        url="https://arxiv.org/abs/1512.03385"
    )
    src2 = SourceRecord(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        year="2017",
        source="NeurIPS",
        url="https://arxiv.org/abs/1706.03762"
    )

    num1 = cm.register_source(src1)
    num2 = cm.register_source(src2)
    num1_again = cm.register_source(src1)

    assert num1 == 1
    assert num2 == 2
    assert num1_again == 1  # Must reuse same citation number!
    assert cm.get_inline_citation(num1) == "[1]"
    assert cm.get_inline_citation(num2) == "[2]"

    # Verify reference list formatting
    citations = cm.get_all_citations()
    assert len(citations) == 2
    ref_list = cm.get_reference_list()
    assert len(ref_list) == 2
    assert "[1] Kaiming He and Xiangyu Zhang" in ref_list[0]
    assert "Deep Residual Learning for Image Recognition" in ref_list[0]
    assert "[2] Ashish Vaswani and Noam Shazeer" in ref_list[1]
    assert "Attention Is All You Need" in ref_list[1]



def test_citation_manager_clean_invalid_citations():
    """Verify CitationManager strips out citations that have no backing registered source."""
    cm = CitationManager()
    src = SourceRecord(title="Valid Source", authors=["A. Researcher"], year="2022")
    cm.register_source(src)  # [1]

    raw_text = "As shown in [1], our method works. But fake reference [99] and [5] should be removed."
    cleaned = cm.clean_invalid_citations(raw_text)

    assert "[1]" in cleaned
    assert "[99]" not in cleaned
    assert "[5]" not in cleaned


# ===========================================================================
# 2. IEEE Formatter & Export Tests
# ===========================================================================

def test_ieee_formatter_and_preview_html():
    """Verify IEEEFormatterService correctly capitalizes sections, sets Roman numerals, and outputs HTML."""
    src = SourceRecord(title="Test Paper", authors=["Jane Doe"], year="2023", source="IEEE Trans")
    cit = Citation(number=1, source=src)

    paper = ResearchPaper(
        paper_id="test-paper-123",
        title="Machine Learning in Cybersecurity",
        authors=["Alice Smith", "Bob Jones"],
        abstract="This paper explores intrusion detection with ML.",
        keywords=["Cybersecurity", "Intrusion Detection", "Machine Learning"],
        sections=[
            PaperSection(
                number="I",
                title="introduction",  # lowercase, should be formatted to uppercase
                content="Cybersecurity threats are evolving rapidly [1].",
                subsections=[
                    PaperSubsection(label="1", title="Background", content="Historical context.")
                ]
            ),
            PaperSection(
                number="II",
                title="Related Work",
                content="Prior work has investigated neural approaches [1]."
            )
        ],
        citations=[cit],
        sources=[src],
        similarity_score=0.08
    )

    formatted_paper = IEEEFormatterService.format_paper(paper)
    assert formatted_paper.sections[0].title == "INTRODUCTION"
    assert formatted_paper.sections[1].title == "RELATED WORK"
    assert formatted_paper.sections[0].subsections[0].label == "A"

    html_preview = IEEEFormatterService.to_html_preview(formatted_paper)
    assert "Machine Learning in Cybersecurity" in html_preview
    assert "Abstract—" in html_preview
    assert "Index Terms—" in html_preview
    assert "I. INTRODUCTION" in html_preview
    assert "REFERENCES" in html_preview
    assert "Jane Doe" in html_preview or "J. Doe" in html_preview

    full_pdf_html = IEEEFormatterService.to_full_pdf_html(formatted_paper)
    assert "<!DOCTYPE html>" in full_pdf_html
    assert "8%" in full_pdf_html


def test_export_docx():
    """Verify ExportService generates valid DOCX bytes."""
    paper = ResearchPaper(
        paper_id="test-paper-docx",
        title="Automated Penetration Testing with AI",
        abstract="Abstract content for test.",
        keywords=["AI", "Penetration Testing"],
        sections=[
            PaperSection(number="I", title="INTRODUCTION", content="Testing introduction.")
        ],
        similarity_score=0.12
    )

    docx_bytes = ExportService.export_docx(paper)
    assert docx_bytes is not None
    assert len(docx_bytes) > 500  # Non-empty binary DOCX
    assert docx_bytes.startswith(b"PK")  # Standard ZIP / DOCX magic bytes


# ===========================================================================
# 3. Workflow B — Restructure Paper Pipeline Test
# ===========================================================================

def test_paper_restructurer_pipeline():
    """Verify PaperRestructurerService extracts non-IEEE paper and maps it into IEEE sections."""
    sample_raw_paper = """
    Deep Neural Networks for Malware Classification
    Alice Johnson and Bob Vance
    
    Abstract:
    This paper presents a convolutional neural network architecture for classifying Windows PE malware binaries.
    
    Keywords: Malware, Deep Learning, Security
    
    Background & Prior Studies:
    Traditional antivirus systems rely heavily on signature-based detection. Recent works have explored static analysis.
    
    Proposed Architecture and Experiments:
    We construct a 12-layer CNN trained on the EMBER 2018 benchmark dataset. The model achieves 98.4% accuracy.
    
    Key Findings:
    The CNN effectively identifies obfuscated code patterns.
    
    Summary and Future Direction:
    In this research, we demonstrated high detection rates for binary analysis.
    """

    mock_llm_mapping = {
        "title": "Deep Neural Networks for Malware Classification",
        "abstract": "This paper presents a convolutional neural network architecture for classifying Windows PE malware binaries.",
        "keywords": ["Malware", "Deep Learning", "Security"],
        "sections": [
            {
                "number": "I",
                "title": "INTRODUCTION",
                "content": "Traditional antivirus systems rely heavily on signature-based detection. Recent works have explored static analysis."
            },
            {
                "number": "II",
                "title": "METHODOLOGY",
                "content": "We construct a 12-layer CNN trained on the EMBER 2018 benchmark dataset. The model achieves 98.4% accuracy."
            },
            {
                "number": "III",
                "title": "RESULTS AND DISCUSSION",
                "content": "The CNN effectively identifies obfuscated code patterns."
            },
            {
                "number": "IV",
                "title": "CONCLUSION",
                "content": "In this research, we demonstrated high detection rates for binary analysis."
            }
        ]
    }

    with patch("app.services.llm.LLMService.map_to_ieee_sections", new=AsyncMock(return_value=mock_llm_mapping)):
        restructurer = PaperRestructurerService()
        result = asyncio.run(restructurer.restructure(sample_raw_paper, filename="malware_paper.txt", paper_id="res-1"))

        assert result.status == PaperStatus.completed
        assert result.paper_type == PaperType.restructured
        assert len(result.sections) == 4
        assert result.sections[0].number == "I"
        assert result.sections[0].title == "INTRODUCTION"
        assert "Traditional antivirus systems" in result.sections[0].content
        assert result.sections[1].number == "II"
        assert result.sections[1].title == "METHODOLOGY"


# ===========================================================================
# 4. Workflow A — Generate Research Paper Pipeline Test
# ===========================================================================

def test_research_generator_pipeline():
    """Verify ResearchGeneratorService runs the multi-stage research generation pipeline."""
    req = GenerateRequest(
        topic="Machine Learning for Medical Image Segmentation",
        domain="Biomedical Engineering",
        length=PaperLength.short,
        num_references=5,
        ieee_format=True
    )

    mock_candidates = [
        {
            "title": "U-Net: Convolutional Networks for Biomedical Image Segmentation",
            "authors": ["Olaf Ronneberger", "Philipp Fischer"],
            "year": "2015",
            "source": "MICCAI",
            "url": "https://arxiv.org/abs/1505.04597",
            "abstract": "We present U-Net for medical image segmentation."
        }
    ]

    mock_outline = {
        "title": "Deep Learning Architectures for Medical Image Segmentation",
        "abstract_hint": "Overview of deep learning architectures applied to MRI and CT image segmentation.",
        "keywords": ["Medical Imaging", "Segmentation", "U-Net", "Deep Learning"],
        "sections": [
            {
                "number": "I",
                "title": "INTRODUCTION",
                "focus": "Clinical importance and challenges of automated segmentation.",
                "target_words": 300
            },
            {
                "number": "II",
                "title": "RELATED WORK",
                "focus": "Evolution from atlas-based methods to U-Net.",
                "target_words": 400
            },
            {
                "number": "III",
                "title": "METHODOLOGY AND ARCHITECTURES",
                "focus": "Encoder-decoder networks and attention gates.",
                "target_words": 400
            },
            {
                "number": "IV",
                "title": "CONCLUSION",
                "focus": "Summary of findings and future research.",
                "target_words": 200
            }
        ]
    }

    mock_section_text = "Medical image segmentation is vital for diagnosis [1]. Automated techniques improve accuracy."
    mock_abstract = "This paper surveys state-of-the-art deep learning methods for medical image segmentation."

    with patch("app.services.online_retriever.OnlineRetrieverService.get_online_candidates", new=AsyncMock(return_value=mock_candidates)), \
         patch("app.services.llm.LLMService.generate_paper_outline", new=AsyncMock(return_value=mock_outline)), \
         patch("app.services.llm.LLMService.generate_section", new=AsyncMock(return_value=mock_section_text)), \
         patch("app.services.llm.LLMService.generate_abstract", new=AsyncMock(return_value=mock_abstract)), \
         patch.object(ResearchGeneratorService, "_run_similarity_check", new=AsyncMock(return_value=0.06)):

        generator = ResearchGeneratorService()
        paper = asyncio.run(generator.generate(req, paper_id="gen-test-1"))

        assert paper.status == PaperStatus.completed
        assert paper.paper_type == PaperType.generated
        assert len(paper.sections) == 4
        assert len(paper.citations) >= 1
        assert paper.citations[0].number == 1
        assert "Olaf Ronneberger" in paper.citations[0].source.authors[0]
        assert paper.abstract == mock_abstract
        assert paper.similarity_score == 0.06



# ===========================================================================
# 5. Paper Store Persistence Tests
# ===========================================================================

def test_paper_store_save_load_and_list():
    """Verify PaperStore saves and retrieves ResearchPaper objects accurately."""
    paper = ResearchPaper(
        paper_id="store-test-1",
        topic="Reinforcement Learning in Robotics",
        title="Deep Reinforcement Learning in Autonomous Robotics",
        status=PaperStatus.completed,
        sections=[PaperSection(number="I", title="INTRODUCTION", content="Robotics intro.")],
        similarity_score=0.05
    )

    PaperStore.save(paper)
    assert PaperStore.exists("store-test-1")

    loaded = PaperStore.load("store-test-1")
    assert loaded is not None
    assert loaded.paper_id == "store-test-1"
    assert loaded.title == "Deep Reinforcement Learning in Autonomous Robotics"
    assert loaded.similarity_score == 0.05
    assert len(loaded.sections) == 1

    papers_list = PaperStore.list_papers(limit=10)
    assert any(p["id"] == "store-test-1" for p in papers_list)

    PaperStore.delete("store-test-1")
    assert not PaperStore.exists("store-test-1")

