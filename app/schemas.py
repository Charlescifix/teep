# app/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Example schema for the chat table
class ChatSchema(BaseModel):
    id: Optional[int]
    user_message: str
    bot_message: Optional[str]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True

# Example schema for the documents table
class DocumentSchema(BaseModel):
    id: Optional[int]
    title: str
    content: str

    class Config:
        orm_mode = True


