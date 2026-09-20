# app/services/embedding_service.py
from typing import List, Sequence

import openai
from app.config import settings

# Initialize your API key
openai.api_key = settings.OPENAI_API_KEY

EMBEDDING_MODEL = "text-embedding-ada-002"
# Dimension of EMBEDDING_MODEL's output. Must match the vector(...) column
# declared in scripts/db_reset.py - Postgres rejects mismatched dimensions.
EMBEDDING_DIM = 1536


def generate_embedding(text: str) -> List[float]:
    """Generate embeddings using OpenAI's text-embedding-ada-002 model."""
    response = openai.Embedding.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response["data"][0]["embedding"]


def to_vector_literal(embedding: Sequence[float]) -> str:
    """
    Format an embedding as a pgvector literal, e.g. '[0.1,0.2,0.3]'.

    Passing the literal and casting it with ::vector in SQL keeps us from having
    to register a psycopg2 type adapter, so plain text() queries work as-is.
    """
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"
