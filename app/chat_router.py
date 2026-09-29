# app/chat_router.py
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.rate_limit import PostgresRateLimiter, build_dependency, resolve_client_ip
from app.request_log import describe_request
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

# Built once at import; the counters themselves live in Postgres, shared by
# every replica, so the configured limit is the limit the service enforces.
_chat_rate_limit = build_dependency(
    PostgresRateLimiter(
        [
            (settings.RATE_LIMIT_PER_MINUTE, 60),
            (settings.RATE_LIMIT_PER_HOUR, 3600),
        ]
    ),
    trusted_hops=settings.TRUSTED_PROXY_HOPS,
    message=(
        "You're sending messages a little too quickly. "
        "Please wait a moment and try again."
    ),
    ipv4_prefix=settings.RATE_LIMIT_IPV4_PREFIX,
    ipv6_prefix=settings.RATE_LIMIT_IPV6_PREFIX,
)


@router.post("/chat", dependencies=[Depends(_chat_rate_limit)])
def chat(
    request: Request,
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
        # The sibling of the handler in app/main.py: a request that satisfies
        # the schema but carries nothing to answer is rejected here instead,
        # and would otherwise be just as invisible in the logs.
        logger.warning(
            "422 empty query from %s: %s parsed=%r",
            resolve_client_ip(request, settings.TRUSTED_PROXY_HOPS),
            describe_request(request),
            payload.user_query if payload else None,
        )
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

    # The retrieved chunks stay server-side. They used to ship in the response,
    # which meant anyone on teep.africa could read the knowledge base verbatim
    # out of the network tab, and walk the whole corpus by varying the question.
    # The titles and scores are in the log above when a reply needs explaining.
    logger.info(
        "Chunks used: %s",
        [(d["title"], round(d["similarity_score"], 3)) for d in docs],
    )

    return {
        "query": user_query,
        "answer": final_answer
    }

