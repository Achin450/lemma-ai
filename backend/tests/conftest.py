import io
import pytest
from pathlib import Path
from docx import Document

# Override settings to use a test database and index BEFORE importing app or other components
from app.config import settings
settings.POSTGRES_DB = "test_lemma"
settings.CELERY_ALWAYS_EAGER = True
settings.ENABLE_ONLINE_RETRIEVAL = False

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session", autouse=True)
def clean_test_db_and_index():
    """Ensures test database tables and ES index are initialized and cleaned up if services are running."""
    import logging
    _logger = logging.getLogger("test_conftest")
    from app.services.database import DatabaseService
    from app.services.elasticsearch_client import get_es_client, initialize_es
    
    db_available = False
    es_available = False

    # Initialize DB (creates extension, tables, HNSW index)
    try:
        DatabaseService.initialize_db()
        db_available = True
    except Exception as e:
        _logger.warning(f"PostgreSQL not available for tests: {e}")
        
    # Initialize Elasticsearch index if reachable
    try:
        es = get_es_client()
        if es.ping():
            initialize_es()
            es_available = True
        else:
            _logger.warning("Elasticsearch ping failed, skipping ES setup.")
    except Exception as e:
        _logger.warning(f"Elasticsearch not available for tests: {e}")

        
    # Truncate tables before tests if DB is up
    if db_available:
        try:
            with DatabaseService.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("TRUNCATE TABLE sentences, documents CASCADE;")
                conn.commit()
        except Exception as e:
            _logger.warning(f"Could not truncate tables: {e}")
        
    # Delete and recreate index for clean test state if ES is up
    if es_available:
        es = get_es_client()
        index_name = "reference_sentences"
        try:
            if es.indices.exists(index=index_name):
                es.indices.delete(index=index_name)
            initialize_es()
        except Exception as e:
            _logger.warning(f"Elasticsearch re-initialization failed: {e}")
    
    yield

    
    # Teardown: truncate tables again
    try:
        with DatabaseService.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE sentences, documents CASCADE;")
            conn.commit()
    except Exception:
        pass

@pytest.fixture(scope="module")
def client():
    """Provides a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_text():
    """Provides a standard multi-sentence plain text string."""
    return (
        "This is the first sentence. It has some text. "
        "Here is the second sentence, which is longer and contains more details! "
        "And this is the third sentence: does it work correctly?"
    )

@pytest.fixture
def create_docx_bytes():
    """Fixture that returns a function to generate DOCX bytes on-the-fly."""
    def _create(paragraphs: list[str]) -> bytes:
        doc = Document()
        for p in paragraphs:
            doc.add_paragraph(p)
        
        doc_io = io.BytesIO()
        doc.save(doc_io)
        return doc_io.getvalue()
    return _create
