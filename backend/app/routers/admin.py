import uuid
import logging
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status

from app.services.database import DatabaseService
from app.services.auth import (
    require_admin, require_instructor, get_current_user,
    generate_institution_code,
)
from app.schemas.auth import (
    InstitutionCreate, InstitutionResponse,
    InviteRequest, InviteResponse,
    RoleUpdateRequest, SeatAllocation, IntegrityMetrics, UserProfile,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin Console"])


# ---------------------------------------------------------------------------
# Institution management
# ---------------------------------------------------------------------------

@router.post("/institutions", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
async def create_institution(payload: InstitutionCreate, _: dict = Depends(require_admin)):
    """Create a new institution (super_admin or institution_admin only)."""
    inst_id = str(uuid.uuid4())
    code = generate_institution_code()
    domain = payload.domain.lower().strip() if payload.domain else None

    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO institutions (id, name, domain, institution_code, max_seats)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (inst_id, payload.name, domain, code, payload.max_seats),
            )
            row = cur.fetchone()
        conn.commit()

    return InstitutionResponse(
        id=str(row["id"]), name=row["name"], domain=row.get("domain"),
        institution_code=row["institution_code"], max_seats=row["max_seats"],
        created_at=str(row["created_at"]),
    )


@router.get("/institutions", response_model=list[InstitutionResponse])
async def list_institutions(_: dict = Depends(require_admin)):
    """List all institutions."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM institutions ORDER BY created_at DESC")
            rows = cur.fetchall()
    return [
        InstitutionResponse(
            id=str(r["id"]), name=r["name"], domain=r.get("domain"),
            institution_code=r["institution_code"], max_seats=r["max_seats"],
            created_at=str(r["created_at"]),
        ) for r in rows
    ]


@router.get("/institutions/{institution_id}/seats", response_model=SeatAllocation)
async def get_seat_allocation(institution_id: str, _: dict = Depends(require_admin)):
    """View seat allocation and member list for an institution."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM institutions WHERE id = %s", (institution_id,))
            inst = cur.fetchone()
            if not inst:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

            cur.execute(
                """SELECT u.*, i.name AS institution_name
                   FROM users u
                   LEFT JOIN institutions i ON u.institution_id = i.id
                   WHERE u.institution_id = %s ORDER BY u.created_at""",
                (institution_id,),
            )
            members = cur.fetchall()

    profiles = [
        UserProfile(
            id=str(m["id"]), email=m["email"], full_name=m["full_name"],
            role=m["role"],
            institution_id=str(m["institution_id"]) if m.get("institution_id") else None,
            institution_name=m.get("institution_name"),
            email_verified=m.get("email_verified", False),
            created_at=str(m.get("created_at", "")),
        ) for m in members
    ]

    return SeatAllocation(
        institution_id=str(inst["id"]),
        institution_name=inst["name"],
        max_seats=inst["max_seats"],
        used_seats=len(profiles),
        available_seats=max(0, inst["max_seats"] - len(profiles)),
        members=profiles,
    )


@router.get("/institutions/{institution_id}/metrics", response_model=IntegrityMetrics)
async def get_institution_metrics(institution_id: str, _: dict = Depends(require_admin)):
    """Aggregate integrity metrics for all submissions by institution members."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check institution exists
            cur.execute("SELECT id FROM institutions WHERE id = %s", (institution_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

            # Aggregate submission stats
            cur.execute(
                """SELECT
                       COUNT(*) AS total,
                       AVG(plagiarism_score) AS avg_plag,
                       AVG(ai_score) AS avg_ai,
                       SUM(CASE WHEN plagiarism_score >= 0.6 THEN 1 ELSE 0 END) AS high_flag,
                       SUM(CASE WHEN plagiarism_score >= 0.3 AND plagiarism_score < 0.6 THEN 1 ELSE 0 END) AS medium_flag,
                       SUM(CASE WHEN plagiarism_score < 0.3 THEN 1 ELSE 0 END) AS clean
                   FROM submissions s
                   JOIN users u ON s.student_id = u.id
                   WHERE u.institution_id = %s AND s.status = 'completed'""",
                (institution_id,),
            )
            stats = cur.fetchone()

    return IntegrityMetrics(
        institution_id=institution_id,
        total_submissions=stats["total"] or 0,
        avg_plagiarism_score=round(float(stats["avg_plag"] or 0), 4),
        avg_ai_score=round(float(stats["avg_ai"] or 0), 4),
        flagged_high=stats["high_flag"] or 0,
        flagged_medium=stats["medium_flag"] or 0,
        clean=stats["clean"] or 0,
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@router.patch("/users/{user_id}/role", status_code=status.HTTP_200_OK)
async def update_user_role(user_id: str, payload: RoleUpdateRequest, _: dict = Depends(require_admin)):
    """Update a user''s role."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET role = %s WHERE id = %s RETURNING id", (payload.role, user_id))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        conn.commit()
    return {"user_id": user_id, "role": payload.role, "message": "Role updated successfully."}


@router.post("/institutions/{institution_id}/invite", response_model=InviteResponse)
async def invite_users(institution_id: str, payload: InviteRequest, _: dict = Depends(require_admin)):
    """
    Bulk-invite users to an institution by email.
    Users who already have accounts are noted but not duplicated.
    """
    invited, already_registered, failed = [], [], []

    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM institutions WHERE id = %s", (institution_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

            for email in payload.emails:
                email = email.lower().strip()
                try:
                    cur.execute("SELECT id, institution_id FROM users WHERE email = %s", (email,))
                    existing = cur.fetchone()
                    if existing:
                        # Update institution if not already assigned
                        if not existing["institution_id"]:
                            cur.execute(
                                "UPDATE users SET institution_id = %s, role = %s WHERE email = %s",
                                (institution_id, payload.role, email),
                            )
                        already_registered.append(email)
                    else:
                        # Pre-register as a pending invite (no password yet — they''ll self-register)
                        # In production, send an email invite link here
                        invited.append(email)
                except Exception as e:
                    logger.error(f"Failed to invite {email}: {e}")
                    failed.append(email)
        conn.commit()

    return InviteResponse(invited=invited, already_registered=already_registered, failed=failed)
