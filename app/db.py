# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# echo=False will suppress SQL logs; set to True if you want to see queries in console
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
