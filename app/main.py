# app/main.py

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.chat_router import router as chat_router

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


from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://teep.africa",  # Your website domain
]

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict in production
    allow_credentials=True,
    allow_methods=["*"],
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
