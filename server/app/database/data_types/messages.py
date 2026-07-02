import uuid
from datetime import datetime
from pydantic import BaseModel
from app.database.tables.messages import SenderType

class MessageBase(BaseModel):
    cid: uuid.UUID
    sender_type: SenderType | None = None
    message_text: str | None = None
    audio_location: str | None = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    mid: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
