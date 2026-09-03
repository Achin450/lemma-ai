import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from app.config import settings

class DatabaseService:
    """Manages PostgreSQL database connections, table creation, and metadata queries."""
    
    @staticmethod
    def get_connection():
        """Returns a connection to the PostgreSQL database with a 5-second connection timeout."""
        db_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
        if db_url:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            return psycopg2.connect(db_url, connect_timeout=5)
            
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            connect_timeout=5
        )
        return conn

    @classmethod
    def initialize_db(cls):
        """Creates the PostgreSQL tables and extensions if they do not already exist."""
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                # Enable pgvector extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # Create documents table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id VARCHAR(255) PRIMARY KEY,
                        title TEXT NOT NULL,
                        author TEXT,
                        source TEXT
                    );
                """)
                
                # Create sentences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sentences (
                        id SERIAL PRIMARY KEY,
                        document_id VARCHAR(255) NOT NULL,
                        sentence_index INT NOT NULL,
                        text TEXT NOT NULL,
                        embedding vector(384),
                        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                    );
                """)
                
                # Create HNSW index on the vector embedding column for fast cosine distance search
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS sentences_embedding_hnsw_idx 
                    ON sentences USING hnsw (embedding vector_cosine_ops);
                """)
                
                # Create institutions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS institutions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT NOT NULL,
                        domain TEXT UNIQUE,
                        institution_code VARCHAR(32) UNIQUE,
                        max_seats INT DEFAULT 100,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'student',
                        institution_id UUID REFERENCES institutions(id) ON DELETE SET NULL,
                        email_verified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                # Create api_keys table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                        key_hash TEXT NOT NULL,
                        label TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        expires_at TIMESTAMPTZ
                    );
                """)
                
                # Create submissions table (for instructor dashboard - Phase 3)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS courses (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
                        instructor_id UUID REFERENCES users(id) ON DELETE SET NULL,
                        name TEXT NOT NULL,
                        course_code VARCHAR(32),
                        semester VARCHAR(32),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS assignments (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        due_date TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS submissions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        assignment_id UUID REFERENCES assignments(id) ON DELETE CASCADE,
                        student_id UUID REFERENCES users(id) ON DELETE SET NULL,
                        job_id VARCHAR(255),
                        filename TEXT,
                        submitted_at TIMESTAMPTZ DEFAULT NOW(),
                        plagiarism_score FLOAT,
                        ai_score FLOAT,
                        status VARCHAR(32) DEFAULT 'pending'
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cross_submission_matches (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        submission_a UUID REFERENCES submissions(id) ON DELETE CASCADE,
                        submission_b UUID REFERENCES submissions(id) ON DELETE CASCADE,
                        similarity_score FLOAT,
                        match_count INT
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lti_platforms (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
                        platform_type VARCHAR(32),
                        client_id TEXT NOT NULL,
                        deployment_id TEXT,
                        auth_url TEXT,
                        token_url TEXT,
                        jwks_url TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_usage_log (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
                        endpoint TEXT,
                        status_code INT,
                        timestamp TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS federation_peers (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        institution_id UUID REFERENCES institutions(id) ON DELETE SET NULL,
                        peer_url TEXT NOT NULL,
                        api_key_hash TEXT NOT NULL,
                        status VARCHAR(32) DEFAULT 'active',
                        last_heartbeat TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS federation_queries (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        source_peer_id UUID REFERENCES federation_peers(id) ON DELETE SET NULL,
                        query_embedding_count INT,
                        results_returned INT,
                        latency_ms INT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
            conn.commit()

    @classmethod
    def clear_db(cls):
        """Clears all records from the tables (useful for tests)."""
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE sentences, documents CASCADE;")
            conn.commit()

    @classmethod
    def get_sentence_count(cls) -> int:
        """Returns the total number of sentences in the database."""
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM sentences;")
                return cursor.fetchone()[0]

    @classmethod
    def insert_reference_document(cls, doc_id: str, title: str, author: str, source: str) -> None:
        """Inserts a document metadata record into the database."""
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO documents (id, title, author, source) 
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE 
                    SET title = EXCLUDED.title, 
                        author = EXCLUDED.author, 
                        source = EXCLUDED.source;
                """
                cursor.execute(query, (doc_id, title, author, source))
            conn.commit()

    @classmethod
    def insert_reference_sentences(cls, sentences: list[dict]) -> None:
        """
        Bulk inserts sentences into the database.
        Each dict in the sentences list must contain:
        {
            "document_id": str,
            "sentence_index": int,
            "text": str,
            "embedding": list[float]
        }
        """
        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                data = [
                    (
                        s["document_id"],
                        s["sentence_index"],
                        s["text"],
                        f"[{','.join(map(str, s['embedding']))}]" if s.get("embedding") is not None else None
                    )
                    for s in sentences
                ]
                query = """
                    INSERT INTO sentences (document_id, sentence_index, text, embedding)
                    VALUES %s
                    ON CONFLICT DO NOTHING;
                """
                execute_values(cursor, query, data)
            conn.commit()

    @classmethod
    def get_sentence_by_faiss_id(cls, sentence_id: int) -> dict | None:
        """Retrieves a sentence and its associated document metadata by its primary key ID (retains backward compatibility)."""
        with cls.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT s.text AS sentence_text, s.document_id, d.title, d.author, d.source
                    FROM sentences s
                    JOIN documents d ON s.document_id = d.id
                    WHERE s.id = %s;
                """, (sentence_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "text": row["sentence_text"],
                        "doc_id": row["document_id"],
                        "doc_title": row["title"],
                        "doc_author": row["author"],
                        "doc_source": row["source"]
                    }
                return None
