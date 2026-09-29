# app/main.py

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

# Validate before importing anything that touches the settings. app.db builds its
# engine at import time, so an empty DATABASE_URL would otherwise surface as
# SQLAlchemy's "Could not parse SQLAlchemy URL from string ''" instead of a
# message naming the variable to set.
settings.validate()

from app.chat_router import router as chat_router  # noqa: E402
from app.db import engine  # noqa: E402
from app.rate_limit import ensure_schema, resolve_client_ip  # noqa: E402
from app.request_log import ERRORS_SNIPPET, clip, describe_request  # noqa: E402

logger = logging.getLogger(__name__)

# The rate limiter keeps its counters in Postgres so they are shared across
# replicas. Creating the table here means a deploy needs no migration step.
ensure_schema(engine)

# Paths
CURRENT_FILE = Path(__file__).resolve()
APP_DIR = CURRENT_FILE.parent
PROJECT_ROOT = APP_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="TEEP RAG Chatbot",
    description="A Retrieval-Augmented Generation chatbot for TEEP.",
    version="0.1.0"
)


# Enable CORS.
#
# This used to pass allow_origins=["*"] while defining an unused `origins` list.
# With allow_credentials=True, Starlette answers a wildcard by echoing back
# whichever Origin asked, so any site could call the API from a browser - on an
# endpoint that has no auth and spends OpenAI credits per call. The list comes
# from ALLOWED_ORIGINS; see app/config.py for the default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Log the requests FastAPI rejects before they reach a route.
#
# These were invisible: a validation failure produced an access-log line and
# nothing else, so a sustained flood of them said only that someone was sending
# something wrong - not what, and not whether it was an attacker or one of our
# own integrations regressing. The response is unchanged, matching FastAPI's
# default handler exactly, because widget.js reads `detail` off it.
@app.exception_handler(RequestValidationError)
async def log_request_validation_error(request: Request, exc: RequestValidationError):
    body = b""
    try:
        # Already read and cached during validation, so this does not block on
        # a client that has stopped sending.
        body = await request.body()
    except Exception:  # pragma: no cover - body is best-effort context only
        pass

    logger.warning(
        "422 rejected from %s: %s errors=%s",
        resolve_client_ip(request, settings.TRUSTED_PROXY_HOPS),
        describe_request(request, body),
        clip(str(exc.errors()), ERRORS_SNIPPET),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


# Health check
@app.get("/health")
def health_check():
    return {"status": "OK"}

# Include the chat routes at /api
app.include_router(chat_router, prefix="/api", tags=["chat"])

# Finally, mount the frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
