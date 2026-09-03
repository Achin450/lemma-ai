"""
Paper Store service — unified persistence for research papers and similarity checks.
Supports:
  1. Generated Research Papers (paper_type='generated')
  2. Restructured IEEE Papers (paper_type='restructured')
  3. Plagiarism / Similarity Checks (paper_type='similarity_check')
Persists to PostgreSQL (research_papers table) and caches JSON to disk (PAPERS_DIR).
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.schemas.research import ResearchPaper, PaperStatus, PaperType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure papers directory exists
# ---------------------------------------------------------------------------
PAPERS_DIR: Path = settings.UPLOAD_DIR.parent / "papers"
try:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.warning(f"Could not create PAPERS_DIR at {PAPERS_DIR}: {e}. Falling back to uploads dir.")
    PAPERS_DIR = settings.UPLOAD_DIR


def _paper_path(paper_id: str) -> Path:
    return PAPERS_DIR / f"{paper_id}.json"


def _sim_path(job_id: str) -> Path:
    return PAPERS_DIR / f"sim_{job_id}.json"


class PaperStore:
    """
    Manages saving, loading, listing, and deleting research items:
    - Generated Research Papers
    - Restructured IEEE Papers
    - Plagiarism & Similarity Reports
    """

    @staticmethod
    def ensure_db_table() -> None:
        """Create or migrate the research_papers table in PostgreSQL."""
        try:
            from app.services.database import DatabaseService
            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS research_papers (
                            id UUID PRIMARY KEY,
                            job_id VARCHAR(255) UNIQUE,
                            user_id UUID,
                            title TEXT,
                            topic TEXT,
                            status VARCHAR(32) DEFAULT 'pending',
                            paper_type VARCHAR(32) DEFAULT 'generated',
                            similarity_score FLOAT,
                            sections_count INT DEFAULT 0,
                            citations_count INT DEFAULT 0,
                            report_data JSONB,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at TIMESTAMPTZ DEFAULT NOW()
                        );
                        ALTER TABLE research_papers ADD COLUMN IF NOT EXISTS sections_count INT DEFAULT 0;
                        ALTER TABLE research_papers ADD COLUMN IF NOT EXISTS citations_count INT DEFAULT 0;
                        ALTER TABLE research_papers ADD COLUMN IF NOT EXISTS report_data JSONB;
                    """)
                conn.commit()
            logger.info("research_papers table ensured in PostgreSQL.")
        except Exception as e:
            logger.warning(f"Could not ensure research_papers table: {e}")

    @staticmethod
    def save(paper: ResearchPaper) -> str:
        """
        Serialize paper to JSON and write to disk, then update PostgreSQL.
        Returns the paper_id.
        """
        if not paper.paper_id:
            paper.paper_id = str(uuid.uuid4())

        try:
            path = _paper_path(paper.paper_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(paper.model_dump(), f, ensure_ascii=False, indent=2)
            logger.info(f"Saved paper {paper.paper_id} to disk at {path}")
        except Exception as e:
            logger.error(f"Failed to save paper {paper.paper_id} to disk: {e}")
            raise

        # Update PostgreSQL metadata
        try:
            PaperStore._upsert_db_record(paper)
        except Exception as e:
            logger.warning(f"Failed to update DB record for paper {paper.paper_id}: {e}")

        return paper.paper_id

    @staticmethod
    def _upsert_db_record(paper: ResearchPaper) -> None:
        """Insert or update the research_papers metadata row in PostgreSQL."""
        try:
            from app.services.database import DatabaseService
            try:
                paper_uuid = str(uuid.UUID(paper.paper_id))
            except (ValueError, AttributeError):
                paper_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(paper.paper_id)))

            sec_count = len(paper.sections) if paper.sections else 0
            cit_count = len(paper.citations) if paper.citations else 0

            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_papers (
                            id, job_id, title, topic, status, paper_type,
                            similarity_score, sections_count, citations_count, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (job_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            topic = EXCLUDED.topic,
                            status = EXCLUDED.status,
                            similarity_score = EXCLUDED.similarity_score,
                            sections_count = EXCLUDED.sections_count,
                            citations_count = EXCLUDED.citations_count,
                            updated_at = NOW();
                    """, (
                        paper_uuid,
                        paper.paper_id,
                        (paper.title or "Untitled Paper")[:500],
                        (paper.topic or "")[:500],
                        paper.status.value,
                        paper.paper_type.value,
                        paper.similarity_score,
                        sec_count,
                        cit_count,
                    ))
                conn.commit()
        except Exception as e:
            logger.warning(f"DB upsert failed for paper {paper.paper_id}: {e}")

    @staticmethod
    def save_similarity_report(
        job_id: str,
        report_dict: dict,
        filename: Optional[str] = None,
        text_preview: Optional[str] = None,
        score: float = 0.0,
    ) -> None:
        """
        Persist a standalone similarity check report to disk and PostgreSQL.
        """
        # 1. Save to disk
        try:
            path = _sim_path(job_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "job_id": job_id,
                    "paper_type": "similarity_check",
                    "title": filename or (f"Similarity: {text_preview[:50]}..." if text_preview else "Plagiarism Check"),
                    "topic": "Plagiarism & Similarity Analysis",
                    "similarity_score": score,
                    "report": report_dict,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved similarity report {job_id} to disk at {path}")
        except Exception as e:
            logger.warning(f"Could not save similarity report {job_id} to disk: {e}")

        # 2. Save to PostgreSQL
        try:
            from app.services.database import DatabaseService
            try:
                rec_uuid = str(uuid.UUID(job_id))
            except (ValueError, AttributeError):
                rec_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(job_id)))

            title = filename or (f"Similarity: {text_preview[:60]}..." if text_preview else "Plagiarism Check")
            total_sents = report_dict.get("total_sentences", 0)
            matched_sents = report_dict.get("matched_sentences", 0)

            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_papers (
                            id, job_id, title, topic, status, paper_type,
                            similarity_score, sections_count, citations_count, report_data, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (job_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            similarity_score = EXCLUDED.similarity_score,
                            sections_count = EXCLUDED.sections_count,
                            citations_count = EXCLUDED.citations_count,
                            report_data = EXCLUDED.report_data,
                            updated_at = NOW();
                    """, (
                        rec_uuid,
                        job_id,
                        title[:500],
                        "Plagiarism & Similarity Analysis",
                        "completed",
                        "similarity_check",
                        score,
                        total_sents,
                        matched_sents,
                        json.dumps(report_dict),
                    ))
                conn.commit()
            logger.info(f"Saved similarity report {job_id} to PostgreSQL research_papers.")
        except Exception as e:
            logger.warning(f"DB upsert failed for similarity check {job_id}: {e}")

    @staticmethod
    def load(paper_id: str) -> Optional[ResearchPaper]:
        """Load a ResearchPaper from disk by paper_id."""
        path = _paper_path(paper_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ResearchPaper.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load paper {paper_id}: {e}")
            return None

    @staticmethod
    def load_similarity_report(job_id: str) -> Optional[dict]:
        """Load a similarity check report from disk or DB."""
        # Check disk first
        path = _sim_path(job_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("report") or data
            except Exception as e:
                logger.warning(f"Failed to load sim report from disk {job_id}: {e}")

        # Check DB
        try:
            from app.services.database import DatabaseService
            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT report_data FROM research_papers WHERE job_id = %s",
                        (job_id,)
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        val = row[0]
                        return json.loads(val) if isinstance(val, str) else val
        except Exception as e:
            logger.warning(f"Failed to load sim report from DB {job_id}: {e}")

        return None

    @staticmethod
    def delete(paper_id: str) -> bool:
        """Delete a paper or similarity check from DB and disk."""
        # 1. Delete from PostgreSQL
        try:
            from app.services.database import DatabaseService
            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM research_papers WHERE job_id = %s OR id::text = %s",
                        (paper_id, paper_id)
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"DB delete failed for paper {paper_id}: {e}")

        # 2. Delete from disk
        deleted = False
        p_path = _paper_path(paper_id)
        if p_path.exists():
            p_path.unlink(missing_ok=True)
            deleted = True

        s_path = _sim_path(paper_id)
        if s_path.exists():
            s_path.unlink(missing_ok=True)
            deleted = True

        return deleted

    @staticmethod
    def exists(paper_id: str) -> bool:
        """Check if a paper exists on disk."""
        return _paper_path(paper_id).exists() or _sim_path(paper_id).exists()

    @staticmethod
    def list_papers(user_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        """
        List all research papers and similarity checks.
        Pulls from PostgreSQL research_papers with disk fallback.
        """
        # Try DB first
        try:
            from app.services.database import DatabaseService
            import psycopg2.extras
            with DatabaseService.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    if user_id:
                        cursor.execute("""
                            SELECT id, job_id, user_id, title, topic, status, paper_type,
                                   similarity_score, sections_count, citations_count,
                                   created_at, updated_at
                            FROM research_papers
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (user_id, limit))
                    else:
                        cursor.execute("""
                            SELECT id, job_id, user_id, title, topic, status, paper_type,
                                   similarity_score, sections_count, citations_count,
                                   created_at, updated_at
                            FROM research_papers
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (limit,))
                    rows = cursor.fetchall()
                    if rows:
                        results = []
                        for r in rows:
                            d = dict(r)
                            # Convert datetime to ISO string
                            if isinstance(d.get("created_at"), datetime):
                                d["created_at"] = d["created_at"].isoformat()
                            if isinstance(d.get("updated_at"), datetime):
                                d["updated_at"] = d["updated_at"].isoformat()
                            if d.get("id"):
                                d["id"] = str(d["id"])
                            if d.get("user_id"):
                                d["user_id"] = str(d["user_id"])
                            results.append(d)
                        return results
        except Exception as e:
            logger.warning(f"Failed to list papers from PostgreSQL: {e}")

        # Fallback: scan JSON files in PAPERS_DIR
        try:
            papers = []
            if PAPERS_DIR.exists():
                for json_file in sorted(PAPERS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            is_sim = json_file.name.startswith("sim_") or data.get("paper_type") == "similarity_check"
                            p_type = "similarity_check" if is_sim else data.get("paper_type", "generated")
                            job_key = data.get("job_id") or data.get("paper_id") or json_file.stem.replace("sim_", "")
                            papers.append({
                                "id": job_key,
                                "job_id": job_key,
                                "title": data.get("title", "Untitled Document"),
                                "topic": data.get("topic", ""),
                                "status": data.get("status", "completed"),
                                "paper_type": p_type,
                                "similarity_score": data.get("similarity_score"),
                                "sections_count": len(data.get("sections", [])) if "sections" in data else 0,
                                "citations_count": len(data.get("citations", [])) if "citations" in data else 0,
                                "created_at": data.get("created_at"),
                            })
                    except Exception:
                        continue
            return papers
        except Exception as e:
            logger.warning(f"Failed to list papers from disk: {e}")
            return []

