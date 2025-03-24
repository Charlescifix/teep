# app/chat_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.retrieval_service import retrieve_relevant_docs
from app.services.llm_service import generate_llm_answer

router = APIRouter()

@router.post("/chat")
def chat(user_query: str, db: Session = Depends(get_db)):
    """
    1) Retrieve the top-k chunks from the documents table
    2) Combine those chunks
    3) Pass them + the user query to the LLM for a final summarized answer
    4) Return both the final answer and the retrieved docs
    """
    # 1. Retrieve relevant docs (e.g., top_k=3 for more context)
    docs = retrieve_relevant_docs(db, user_query, top_k=3)

    # 2. Combine doc content into one large string
    combined_context = "\n".join([d["content"] for d in docs])

    # 3. Ask the LLM for a final summarized answer
    final_answer = generate_llm_answer(user_query, combined_context)

    # 4. Return both the relevant chunks and the final summarized answer
    return {
        "query": user_query,
        "relevant_docs": docs,
        "answer": final_answer
    }
