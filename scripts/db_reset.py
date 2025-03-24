# scripts/db_reset.py
from sqlalchemy import create_engine, text
from app.config import settings

def reset_db():
    engine = create_engine(settings.DATABASE_URL, echo=True)

    with engine.connect() as conn:
        # Drop existing tables
        drop_sql = text("""
            DROP TABLE IF EXISTS chat;
            DROP TABLE IF EXISTS chats;
            DROP TABLE IF EXISTS documents;
        """)
        conn.execute(drop_sql)

        # Create new tables
        create_sql = text("""
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
                embedding float[]
            );
        """)
        conn.execute(create_sql)

        conn.commit()

if __name__ == "__main__":
    reset_db()

