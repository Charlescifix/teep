# app/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class ChatRequest(BaseModel):
    """
    JSON body for POST /api/chat.

    The endpoint also still accepts ?user_query= as a query parameter, which is
    how the bundled widget in frontend/index.html calls it.
    """
    user_query: str = Field(
        ...,
        min_length=1,
        description="User's question about TEEP",
    )


# Example schema for the chat table
class ChatSchema(BaseModel):
    # Pydantic v2 renamed orm_mode to from_attributes, and no longer infers a
    # None default from Optional - without "= None" these fields are required.
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_message: str
    bot_message: Optional[str] = None
    created_at: Optional[datetime] = None


# Example schema for the documents table
class DocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    title: str
    content: str


