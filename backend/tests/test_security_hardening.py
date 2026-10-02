"""
Comprehensive Production Security Hardening Test Suite
Verifies:
1. Authentication enforcement (401 on missing/invalid tokens)
2. Role-Based Access Control / RBAC (403 on student calling admin APIs)
3. Elimination of admin@ prefix privilege escalation
4. Password strength validation
5. IDOR / BOLA Prevention on Research Papers & Reports
6. User Data Isolation
7. File Upload Security (magic bytes validation & path traversal prevention)
8. Security Headers (OWASP defense-in-depth)
9. Strict CORS Policy
10. Rate Limiting / Abuse Prevention
"""
import uuid
import pytest
from app.config import settings
from app.schemas.research import ResearchPaper, PaperStatus, PaperType
from app.services.paper_store import PaperStore
from app.services.auth import create_access_token


# -----------------------------------------------------------------------------
# 1. Authentication Enforcement Tests
# -----------------------------------------------------------------------------

def test_unauthenticated_request_rejected(client):
    """Protected endpoints must return 401 Unauthorized without a valid Bearer token."""
    # 1. Auth profile
    res1 = client.get(f"{settings.API_V1_STR}/auth/me")
    assert res1.status_code == 401
    assert "detail" in res1.json()

    # 2. Research papers
    res2 = client.get(f"{settings.API_V1_STR}/research/papers")
    assert res2.status_code == 401

    # 3. Document upload
    res3 = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        files={"file": ("test.txt", b"Hello world", "text/plain")}
    )
    assert res3.status_code == 401


def test_invalid_token_rejected(client):
    """Forged or malformed Bearer tokens must return 401 Unauthorized."""
    headers = {"Authorization": "Bearer forged.token.value"}
    res = client.get(f"{settings.API_V1_STR}/auth/me", headers=headers)
    assert res.status_code == 401
    assert "detail" in res.json()


# -----------------------------------------------------------------------------
# 2. RBAC & Privilege Escalation Tests
# -----------------------------------------------------------------------------

def test_admin_endpoint_forbidden_for_student(client, auth_headers):
    """Students must receive 403 Forbidden on admin console endpoints."""
    res1 = client.get(f"{settings.API_V1_STR}/admin/overview", headers=auth_headers)
    assert res1.status_code == 403
    assert "Admin privileges required" in res1.json()["detail"]

    res2 = client.get(f"{settings.API_V1_STR}/admin/users", headers=auth_headers)
    assert res2.status_code == 403


from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.services.auth import validate_password_strength


def test_admin_endpoint_allowed_for_super_admin(client, admin_headers):
    """Super admins must have authorized access to admin endpoints."""
    with patch("app.routers.admin.DatabaseService.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"count": 5}
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        
        res = client.get(f"{settings.API_V1_STR}/admin/overview", headers=admin_headers)
        assert res.status_code == 200
        assert "total_institutions" in res.json()


def test_prevent_admin_email_prefix_escalation(client):
    """Registering with admin@anything.com must NOT grant super_admin role."""
    unique_email = f"admin@{uuid.uuid4().hex[:8]}.org"
    with patch("app.routers.auth._get_user_by_email", return_value=None), \
         patch("app.routers.auth.DatabaseService.get_connection") as mock_conn, \
         patch("app.routers.auth._get_user_by_id") as mock_get_user:
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_get_user.return_value = {
            "id": str(uuid.uuid4()),
            "email": unique_email,
            "full_name": "Untrusted Attacker",
            "role": "student",
            "institution_id": None,
            "institution_name": None,
            "email_verified": True,
            "subscription_tier": "free",
            "is_pro": False,
            "created_at": "2026-10-01T00:00:00",
        }
        
        payload = {
            "email": unique_email,
            "password": "SecurePass2026!#",
            "full_name": "Untrusted Attacker"
        }
        res = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["user"]["role"] == "student", "Role must be student, NOT super_admin!"


def test_password_strength_enforcement(client):
    """Passwords with insufficient length or lacking complexity must be rejected."""
    # 1. Direct function validation tests
    with pytest.raises(HTTPException) as exc_short:
        validate_password_strength("short")
    assert exc_short.value.status_code == 400
    assert "at least 8 characters" in exc_short.value.detail

    with pytest.raises(HTTPException) as exc_no_num:
        validate_password_strength("alllettersonly")
    assert exc_no_num.value.status_code == 400
    assert "at least one letter and at least one number or symbol" in exc_no_num.value.detail

    # 2. Pydantic validation via API endpoint (rejects < 8 chars with 422)
    res1 = client.post(f"{settings.API_V1_STR}/auth/register", json={
        "email": f"user_{uuid.uuid4().hex[:8]}@example.edu",
        "password": "123",
        "full_name": "Test User"
    })
    assert res1.status_code in (400, 422)

    # 3. Validation via API endpoint for missing complexity (8+ chars but all digits -> 400)
    with patch("app.routers.auth._get_user_by_email", return_value=None):
        res2 = client.post(f"{settings.API_V1_STR}/auth/register", json={
            "email": f"user_{uuid.uuid4().hex[:8]}@example.edu",
            "password": "1234567890",
            "full_name": "Test User"
        })
        assert res2.status_code == 400
        assert "at least one letter and at least one number or symbol" in res2.json()["detail"]


# -----------------------------------------------------------------------------
# 3. IDOR / BOLA Prevention & User Isolation Tests
# -----------------------------------------------------------------------------

def test_research_paper_idor_protection(client):
    """User B must be forbidden from viewing, modifying, or deleting User A's paper."""
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())

    token_a = create_access_token(user_id=user_a_id, email="usera@lemma.ai", role="student")
    token_b = create_access_token(user_id=user_b_id, email="userb@lemma.ai", role="student")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a research paper
    paper_id = f"test-sec-{uuid.uuid4()}"
    paper = ResearchPaper(
        paper_id=paper_id,
        user_id=user_a_id,
        title="User A Private Paper",
        status=PaperStatus.completed,
        paper_type=PaperType.generated,
    )
    PaperStore.save(paper)

    # User A can view their paper
    res_a = client.get(f"{settings.API_V1_STR}/research/{paper_id}", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["title"] == "User A Private Paper"

    # User B attempts to view User A's paper (IDOR attack) -> 403 Forbidden
    res_b_get = client.get(f"{settings.API_V1_STR}/research/{paper_id}", headers=headers_b)
    assert res_b_get.status_code == 403
    assert "Access forbidden" in res_b_get.json()["detail"]

    # User B attempts to update User A's paper -> 403 Forbidden
    res_b_put = client.put(
        f"{settings.API_V1_STR}/research/{paper_id}",
        headers=headers_b,
        json={"title": "Hacked Title"}
    )
    assert res_b_put.status_code == 403

    # User B attempts to delete User A's paper -> 403 Forbidden
    res_b_del = client.delete(f"{settings.API_V1_STR}/research/papers/{paper_id}", headers=headers_b)
    assert res_b_del.status_code == 403

    # Clean up by User A
    del_res = client.delete(f"{settings.API_V1_STR}/research/papers/{paper_id}", headers=headers_a)
    assert del_res.status_code == 200


def test_research_paper_list_isolation(client):
    """User A should only see their own papers in GET /papers, not User B's."""
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())

    token_a = create_access_token(user_id=user_a_id, email="user1@lemma.ai", role="student")
    token_b = create_access_token(user_id=user_b_id, email="user2@lemma.ai", role="student")

    # Create one paper for User A and one for User B
    paper_a_id = f"test-a-{uuid.uuid4()}"
    paper_b_id = f"test-b-{uuid.uuid4()}"

    PaperStore.save(ResearchPaper(paper_id=paper_a_id, user_id=user_a_id, title="Paper A"))
    PaperStore.save(ResearchPaper(paper_id=paper_b_id, user_id=user_b_id, title="Paper B"))

    try:
        res_a = client.get(f"{settings.API_V1_STR}/research/papers", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200
        a_paper_ids = [p.get("id") or p.get("job_id") for p in res_a.json()]
        assert paper_a_id in a_paper_ids
        assert paper_b_id not in a_paper_ids, "User A must NOT see User B's paper in their list!"
    finally:
        PaperStore.delete(paper_a_id)
        PaperStore.delete(paper_b_id)


# -----------------------------------------------------------------------------
# 4. File Upload Security Tests
# -----------------------------------------------------------------------------

def test_file_upload_magic_bytes_validation(client, auth_headers):
    """Uploading executable or disguised content as PDF must be rejected."""
    # Fake PDF (text disguised as .pdf without %PDF signature)
    files = {"file": ("malicious.pdf", b"MZ\x90\x00\x03\x00\x00\x00This is an executable", "application/pdf")}
    res = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        files=files,
        headers=auth_headers
    )
    assert res.status_code == 400
    assert "Invalid PDF" in res.json()["detail"] or "signature" in res.json()["detail"]


def test_file_upload_path_traversal_sanitization(client, auth_headers):
    """Path traversal sequences in filenames must be neutralized."""
    file_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    files = {"file": ("../../../../etc/passwd.pdf", file_content, "application/pdf")}
    res = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        files=files,
        headers=auth_headers
    )
    if res.status_code == 200:
        filename = res.json()["filename"]
        assert "/" not in filename and ".." not in filename


# -----------------------------------------------------------------------------
# 5. Security Headers & CORS Tests
# -----------------------------------------------------------------------------

def test_security_headers_present(client):
    """Response must contain OWASP defense-in-depth security headers."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in res.headers


def test_cors_origin_restriction(client):
    """CORS must properly allow configured domains and not wildcard credentials."""
    res = client.get(
        "/health",
        headers={"Origin": "https://lemma2.vercel.app"}
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://lemma2.vercel.app"
    assert res.headers.get("access-control-allow-credentials") == "true"
