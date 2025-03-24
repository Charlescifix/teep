# app/chat_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.retrieval_service import retrieve_relevant_docs
from app.services.llm_service import generate_llm_answer

router = APIRouter()

@router.post("/chat")
def chat(
    user_query: str = Query(..., description="User's question about TEEP"),
    db: Session = Depends(get_db)
):
    # 1) retrieve top docs
    docs = retrieve_relevant_docs(db, user_query, top_k=3)

    # 2) combine doc contents
    combined_context = "\n".join(d["content"] for d in docs)

    # 3) LLM final answer
    final_answer = generate_llm_answer(user_query, combined_context)

    return {
        "query": user_query,
        "relevant_docs": docs,
        "answer": final_answer
    }
