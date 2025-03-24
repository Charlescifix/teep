# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chat_router import router as chat_router

app = FastAPI(
    title="TEEP RAG Chatbot",
    description="A Retrieval-Augmented Generation chatbot for TEEP.",
    version="0.1.0"
)

# Enable CORS for all domains (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """
    Root endpoint.
    Visiting https://<your-railway-url>/ will show this message.
    """
    return {"message": "Welcome to TEEP RAG Chatbot on Railway! Visit /docs for API docs or /api/chat for the chatbot endpoint."}

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Visiting /health returns {"status": "OK"} if the app is running.
    """
    return {"status": "OK"}

# Include your chat router under /api
app.include_router(chat_router, prefix="/api", tags=["chat"])
