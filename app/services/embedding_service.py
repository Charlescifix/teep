# app/services/embedding_service.py
import openai
from app.config import settings

# Initialize your API key
openai.api_key = settings.OPENAI_API_KEY

def generate_embedding(text: str) -> list[float]:
    """Generate embeddings using OpenAI's text-embedding-ada-002 model."""
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response["data"][0]["embedding"]
