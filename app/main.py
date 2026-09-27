# app/main.py

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

# Validate before importing anything that touches the settings. app.db builds its
# engine at import time, so an empty DATABASE_URL would otherwise surface as
# SQLAlchemy's "Could not parse SQLAlchemy URL from string ''" instead of a
# message naming the variable to set.
settings.validate()

from app.chat_router import router as chat_router  # noqa: E402

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

# Health check
@app.get("/health")
def health_check():
    return {"status": "OK"}

# Include the chat routes at /api
app.include_router(chat_router, prefix="/api", tags=["chat"])

# Finally, mount the frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
