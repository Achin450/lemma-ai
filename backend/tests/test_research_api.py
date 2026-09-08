"""
API Route tests for Lemma AI Research Paper Assistant endpoints.
Tests:
- POST /api/v1/research/generate
- POST /api/v1/research/restructure
- GET  /api/v1/research/status/{job_id}
- GET  /api/v1/research/{paper_id}
- GET  /api/v1/research/export/{paper_id}
- POST /api/v1/research/{paper_id}/improve
- GET  /api/v1/research/list
- POST /api/v1/plagiarism/check
- GET  /api/v1/plagiarism/status/{job_id}
- POST /api/v1/plagiarism/improve
"""

import pytest
import io
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import create_access_token
from app.schemas.research import ResearchPaper, PaperSection, PaperStatus, PaperType, Citation, SourceRecord
from app.services.paper_store import PaperStore

# Generate valid JWT test token with student role
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
TEST_TOKEN = create_access_token(TEST_USER_ID, "testuser@university.edu", "student")
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}

client = TestClient(app)


def test_api_generate_research_paper_endpoint():
    """Verify POST /api/v1/research/generate enqueues task and returns job_id."""
    with patch("app.tasks.research_tasks.generate_paper_task.apply_async") as mock_task:
        mock_task.return_value = MagicMock(id="mock-celery-job-1")

        payload = {
            "topic": "Deep Learning for Autonomous Vehicles",
            "domain": "Computer Science",
            "length": "short",
            "num_references": 5,
            "ieee_format": True
        }

        response = client.post("/api/v1/research/generate", json=payload, headers=AUTH_HEADERS)
        assert response.status_code in (200, 202)
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"


def test_api_restructure_paper_endpoint():
    """Verify POST /api/v1/research/restructure accepts multipart upload and enqueues task."""
    with patch("app.tasks.research_tasks.restructure_paper_task.apply_async") as mock_task:
        mock_task.return_value = MagicMock(id="mock-restructure-job-1")

        file_content = b"Sample raw academic document text with multiple sections."
        files = {
            "file": ("sample_paper.txt", io.BytesIO(file_content), "text/plain")
        }
        data = {"preserve_citations": "true"}

        response = client.post("/api/v1/research/restructure", files=files, data=data, headers=AUTH_HEADERS)
        assert response.status_code in (200, 202)
        res_data = response.json()
        assert "job_id" in res_data
        assert res_data["status"] == "pending"




def test_api_get_paper_and_export():
    """Verify GET /api/v1/research/{paper_id} and export endpoints."""
    paper = ResearchPaper(
        paper_id="api-test-paper-1",
        user_id=TEST_USER_ID,
        title="Federated Learning in Mobile Computing",
        abstract="Abstract on privacy-preserving ML.",
        keywords=["Federated Learning", "Privacy"],
        sections=[
            PaperSection(number="I", title="INTRODUCTION", content="Intro to FL."),
            PaperSection(number="II", title="CONCLUSION", content="Conclusion on FL.")
        ],
        citations=[
            Citation(number=1, source=SourceRecord(title="FL Survey", authors=["John Doe"], year="2021"))
        ],
        similarity_score=0.07,
        status=PaperStatus.completed
    )
    PaperStore.save(paper)

    # 1. Get paper JSON
    response = client.get(f"/api/v1/research/{paper.paper_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    p_data = response.json()
    assert p_data["title"] == "Federated Learning in Mobile Computing"
    assert len(p_data["sections"]) == 2

    # 2. Export DOCX
    docx_resp = client.get(f"/api/v1/research/export/{paper.paper_id}?format=docx", headers=AUTH_HEADERS)
    assert docx_resp.status_code == 200
    assert docx_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(docx_resp.content) > 500

    # 3. List papers
    list_resp = client.get("/api/v1/research/list", headers=AUTH_HEADERS)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert isinstance(list_data, (list, dict))

    # Cleanup
    PaperStore.delete(paper.paper_id)


def test_api_update_paper_with_subsections():
    """Verify PUT /api/v1/research/{paper_id} updates title, abstract, sections, and subsections."""
    paper = ResearchPaper(
        paper_id="api-test-update-1",
        user_id=TEST_USER_ID,
        title="Original Title",
        abstract="Original abstract",
        keywords=["Original"],
        sections=[
            PaperSection(number="I", title="ORIGINAL SECTION", content="Orig content", subsections=[])
        ],
        status=PaperStatus.completed
    )
    PaperStore.save(paper)

    update_payload = {
        "title": "Updated Title via Edit Mode",
        "abstract": "Updated abstract content",
        "keywords": ["AI", "Editing"],
        "authors": ["Lead Researcher", "Co-Author"],
        "sections": [
            {
                "number": "I",
                "title": "UPDATED SECTION",
                "content": "Updated section body",
                "subsections": [
                    {
                        "label": "A",
                        "title": "Updated Subsection Title",
                        "content": "Updated subsection body content"
                    }
                ]
            }
        ]
    }

    put_resp = client.put(f"/api/v1/research/{paper.paper_id}", json=update_payload, headers=AUTH_HEADERS)
    assert put_resp.status_code == 200
    res_data = put_resp.json()
    assert res_data["title"] == "Updated Title via Edit Mode"
    assert res_data["abstract"] == "Updated abstract content"
    assert res_data["authors"] == ["Lead Researcher", "Co-Author"]
    assert len(res_data["sections"]) == 1
    assert res_data["sections"][0]["title"] == "UPDATED SECTION"
    assert len(res_data["sections"][0]["subsections"]) == 1
    assert res_data["sections"][0]["subsections"][0]["title"] == "Updated Subsection Title"
    assert res_data["sections"][0]["subsections"][0]["content"] == "Updated subsection body content"

    # Cleanup
    PaperStore.delete(paper.paper_id)


def test_api_plagiarism_check_text_mode():
    """Verify POST /api/v1/plagiarism/check enqueues task and returns job_id."""
    with patch("app.tasks.research_tasks.similarity_check_task.apply_async") as mock_task:
        mock_task.return_value = MagicMock(id="mock-sim-job-1")


        response = client.post(
            "/api/v1/plagiarism/check",
            data={"text": "This is a sample academic text with over fifty characters to pass validation."},
            headers=AUTH_HEADERS
        )
        assert response.status_code in (200, 202)

        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"


def test_api_plagiarism_improve_endpoint():
    """Verify POST /api/v1/plagiarism/improve rewrites text."""
    with patch("app.services.llm.LLMService.improve_section_similarity", new=AsyncMock(return_value="Rewritten passage with preserved meaning.")):
        response = client.post(
            "/api/v1/plagiarism/improve",
            json={
                "passage": "Original text with high similarity.",
                "context": "Context information.",
                "topic": "Quantum Computing"
            },
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert "improved_text" in data
        assert "Rewritten passage" in data["improved_text"]
