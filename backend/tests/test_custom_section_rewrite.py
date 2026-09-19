"""
Unit Tests for Custom Section Matter Rewriting Endpoint
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.paper_store import PaperStore
from app.schemas.research import ResearchPaper, PaperSection, PaperStatus, PaperType

client = TestClient(app)


def test_custom_rewrite_section_abstract_and_body():
    """Verify that user can customize both Abstract and body sections with prompts."""
    paper_id = f"test-paper-{uuid.uuid4().hex[:8]}"

    paper = ResearchPaper(
        paper_id=paper_id,
        title="Deep Reinforcement Learning in Autonomous Robotics",
        topic="Deep Reinforcement Learning in Autonomous Robotics",
        domain="Robotics & Control",
        status=PaperStatus.completed,
        abstract="Original baseline abstract discussing robotics.",
        sections=[
            PaperSection(
                number="I",
                title="INTRODUCTION",
                content="This is the original introduction discussing robotics background [1]."
            ),
            PaperSection(
                number="IV",
                title="SYSTEM ARCHITECTURE AND PROPOSED METHODOLOGY",
                content="The proposed methodology uses an actor-critic neural network [2]."
            )
        ]
    )
    PaperStore.save(paper)

    # 1. Custom rewrite Abstract
    abstract_payload = {
        "paper_id": paper_id,
        "section_number": "abstract",
        "custom_instruction": "Highlight 95% accuracy and state-of-the-art benchmark results in autonomous navigation.",
        "style": "concise_crisp"
    }
    res_abs = client.post(f"/api/v1/research/{paper_id}/custom-rewrite-section", json=abstract_payload)
    assert res_abs.status_code == 200, f"Abstract rewrite failed: {res_abs.text}"
    data_abs = res_abs.json()
    assert data_abs["section_number"] == "Abstract"
    assert len(data_abs["updated_content"]) > 10

    # 2. Custom rewrite Section IV with math
    sec_payload = {
        "paper_id": paper_id,
        "section_number": "IV",
        "custom_instruction": "Incorporate mathematical Bellman optimality equation and multi-agent loss function.",
        "style": "mathematical"
    }
    res_sec = client.post(f"/api/v1/research/{paper_id}/custom-rewrite-section", json=sec_payload)
    assert res_sec.status_code == 200, f"Section IV rewrite failed: {res_sec.text}"
    data_sec = res_sec.json()
    assert data_sec["section_number"] == "IV"
    assert len(data_sec["updated_content"]) > 20

    # 3. Verify PaperStore has updated content
    reloaded = PaperStore.load(paper_id)
    assert reloaded is not None
    assert reloaded.abstract == data_abs["updated_content"]
    assert reloaded.sections[1].content == data_sec["updated_content"]
