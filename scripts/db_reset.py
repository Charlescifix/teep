# scripts/db_reset.py
from sqlalchemy import create_engine, text
from app.config import settings
from app.rate_limit import ensure_schema
from app.services.embedding_service import EMBEDDING_DIM

# HNSW indexing landed in pgvector 0.5.0. Older servers still run correctly,
# they just fall back to an exact (sequential) scan.
MIN_HNSW_VERSION = (0, 5, 0)


def _pgvector_version(conn) -> tuple:
    raw = conn.execute(text(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    )).scalar()
    parts = []
    for piece in (raw or "0").split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def reset_db():
    engine = create_engine(settings.DATABASE_URL, echo=False)

    with engine.connect() as conn:
        # pgvector ships with Railway's Postgres image but is not enabled by default
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

        version = _pgvector_version(conn)
        print(f"pgvector extension enabled (version {'.'.join(map(str, version))})")

        # Drop existing tables. rate_limit_hits holds nothing worth keeping -
        # the counters refill within an hour of traffic.
        drop_sql = text("""
            DROP TABLE IF EXISTS chat;
            DROP TABLE IF EXISTS chats;
            DROP TABLE IF EXISTS documents;
            DROP TABLE IF EXISTS rate_limit_hits;
        """)
        conn.execute(drop_sql)

        # Create new tables. `embedding` is a native pgvector column now, so
        # similarity is computed in Postgres instead of in Python.
        create_sql = text(f"""
            CREATE TABLE chats (
                id SERIAL PRIMARY KEY,
                user_message TEXT NOT NULL,
                bot_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE documents (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255),
                content TEXT,
                embedding vector({EMBEDDING_DIM})
            );
        """)
        conn.execute(create_sql)
        conn.commit()
        print(f"Tables created: chats, documents (embedding vector({EMBEDDING_DIM}))")

        # Shared counters for the per-IP rate limiter. The app creates this on
        # startup too, so a deploy never needs a migration; it is repeated here
        # so a reset leaves a complete schema behind.
        ensure_schema(engine)
        print("Table created: rate_limit_hits (per-IP rate limiter)")

        # vector_cosine_ops matches the <=> operator used by the retrieval query.
        # An HNSW index builds fine on an empty table, unlike ivfflat, which needs
        # rows present to pick sensible centroids.
        if version >= MIN_HNSW_VERSION:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
                ON documents USING hnsw (embedding vector_cosine_ops)
            """))
            conn.commit()
            print("Index created: documents_embedding_hnsw_idx (hnsw, cosine)")
        else:
            print(
                "WARNING: pgvector < 0.5.0 has no HNSW support, skipping the index. "
                "Queries stay correct but run an exact scan."
            )


if __name__ == "__main__":
    reset_db()
