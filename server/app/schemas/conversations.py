from pydantic import BaseModel
import uuid
from datetime import datetime

class MessageCreate(BaseModel):
    conversation_id: str | None = None
    message_text: str

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    message_text: str
    created_at: str

class ConversationResponse(BaseModel):
    id: str
    status: str
    started_at: str
    ended_at: str | None
    messages: list[MessageResponse]

class ConversationUpdate(BaseModel):
    status: str | None = None
    detected_language: str | None = None
