# app/chat_router.py
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
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
    user_query: str = Query(..., description="User's question about TEEP"),
    db: Session = Depends(get_db)
):
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
