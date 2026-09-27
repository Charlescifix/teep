# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# echo=False will suppress SQL logs; set to True if you want to see queries in console
#
# pool_pre_ping tests a pooled connection before handing it out. Railway reaches
# Postgres through a proxy that drops idle connections, so without this the first
# request after a quiet spell fails on a stale socket. pool_recycle retires
# connections before the proxy does.
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
