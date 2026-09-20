# app/services/retrieval_service.py

from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.embedding_service import generate_embedding, to_vector_literal

# <=> is pgvector's cosine *distance* operator (0 = identical, 2 = opposite).
# Ordering by the bare operator is what lets the HNSW index serve the query -
# wrapping it in an expression like `1 - (...)` would force a sequential scan.
_SEARCH_SQL = text("""
    SELECT
        id,
        title,
        content,
        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity_score
    FROM documents
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:query_embedding AS vector)
    LIMIT :top_k
""")


def retrieve_relevant_docs(db: Session, user_query: str, top_k: int = 3) -> List[Dict]:
    """
    Retrieves the top_k most relevant documents from the 'documents' table by:
      1. Generating an embedding for the user_query.
      2. Letting Postgres rank rows by cosine distance via the pgvector index.
      3. Returning the top_k rows, best match first.

    Only top_k rows cross the wire, so cost no longer scales with corpus size.
    """
    # 1) Generate an embedding for the user query
    query_embedding = generate_embedding(user_query)

    # 2) Rank and slice in the database
    rows = db.execute(_SEARCH_SQL, {
        "query_embedding": to_vector_literal(query_embedding),
        "top_k": top_k,
    }).fetchall()

    # 3) Shape the rows the way chat_router expects them
    return [
        {
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "similarity_score": float(row.similarity_score),
        }
        for row in rows
    ]
