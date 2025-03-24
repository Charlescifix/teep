# app/services/retrieval_service.py

from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np

from app.services.embedding_service import generate_embedding

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors (Python lists).
    """
    v1 = np.array(vec1, dtype=float)
    v2 = np.array(vec2, dtype=float)
    if v1.size == 0 or v2.size == 0:
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

def retrieve_relevant_docs(db: Session, user_query: str, top_k: int = 3) -> List[Dict]:
    """
    Retrieves the top_k most relevant documents from the 'documents' table by:
      1. Generating an embedding for the user_query.
      2. Fetching all documents + their embeddings from the DB.
      3. Computing local cosine similarity in Python.
      4. Sorting by highest similarity score and returning top_k.
    """
    # 1) Generate an embedding for the user query
    query_embedding = generate_embedding(user_query)

    # 2) Fetch documents (id, title, content, embedding) from the DB
    #    Must wrap the SQL in `text(...)` for SQLAlchemy 2.x or strict mode
    sql = text("SELECT id, title, content, embedding FROM documents")
    rows = db.execute(sql).fetchall()

    # 3) Calculate cosine similarity between the query embedding and each doc embedding
    scored_docs = []
    for row in rows:
        doc_id, title, content, doc_embedding = row
        if doc_embedding:  # Make sure it's not NULL / empty
            score = cosine_similarity(query_embedding, doc_embedding)
        else:
            score = 0.0

        scored_docs.append({
            "id": doc_id,
            "title": title,
            "content": content,
            "similarity_score": score
        })

    # 4) Sort documents by descending similarity
    scored_docs.sort(key=lambda x: x["similarity_score"], reverse=True)

    # 5) Return top_k
    return scored_docs[:top_k]
