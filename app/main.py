# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chat_router import router as chat_router

# Create the FastAPI application
app = FastAPI(
    title="TEEP RAG Chatbot",
    description="A Retrieval-Augmented Generation chatbot for TEEP.",
    version="0.1.0"
)

# Add CORS middleware so your frontend at localhost:8080 (or any domain) can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with ["http://localhost:8080"] or your actual front-end domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple health check endpoint
@app.get("/health")
def health_check():
    return {"status": "OK"}

# Include your chat router (assumes you have a file app/chat_router.py
# containing `router = APIRouter()` with your /chat endpoint)
app.include_router(chat_router, prefix="/api", tags=["chat"])
