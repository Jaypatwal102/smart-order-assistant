import uuid
from datetime import datetime
from pydantic import BaseModel
from app.database.tables.conversations import ConversationStatus

class ConversationBase(BaseModel):
    uid: uuid.UUID
    status: ConversationStatus | None = None

class ConversationCreate(ConversationBase):
    pass

class ConversationResponse(ConversationBase):
    cid: uuid.UUID
    started_at: datetime

    class Config:
        from_attributes = True
