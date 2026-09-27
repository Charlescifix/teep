# app/chat_router.py
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChatRequest
from app.services.retrieval_service import retrieve_relevant_docs
from app.services.llm_service import generate_llm_answer

# 1) Create a module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or DEBUG, WARNING, etc.

# Optionally add a handler + formatter if none are configured globally
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(console_handler)

router = APIRouter()

@router.post("/chat")
def chat(
    payload: Optional[ChatRequest] = Body(
        None,
        description='JSON body, e.g. {"user_query": "How long do refunds take?"}',
    ),
    user_query: Optional[str] = Query(
        None,
        description="User's question about TEEP. Alternative to the JSON body.",
    ),
    db: Session = Depends(get_db),
):
    """
    Answer a question about TEEP from the seeded knowledge base.

    The question can arrive either way:
      - JSON body:      {"user_query": "..."}   (preferred)
      - query string:   /api/chat?user_query=...

    Both are supported because frontend/index.html POSTs the query string with an
    empty body, so making the body required would break the bundled widget. When
    both are present the body wins.
    """
    user_query = payload.user_query if payload else user_query
    if not user_query or not user_query.strip():
        raise HTTPException(
            status_code=422,
            detail="user_query is required, as a JSON body field or a query parameter.",
        )

    # 2) Log the incoming user query
    logger.info(f"Received user query: {user_query}")

    # 3) Retrieve docs
    docs = retrieve_relevant_docs(db, user_query, top_k=3)
    logger.info(f"Top docs retrieved (count={len(docs)}).")

    # 4) Combine docs & generate final answer
    combined_context = "\n".join(d["content"] for d in docs)
    final_answer = generate_llm_answer(user_query, combined_context)

    # 5) Log the final answer (you might want to limit length if it's very long)
    logger.info(f"Final answer: {final_answer[:200]}...")  # snippet if large

    return {
        "query": user_query,
        "relevant_docs": docs,
        "answer": final_answer
    }

