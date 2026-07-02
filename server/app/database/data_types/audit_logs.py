import uuid
from datetime import datetime
from pydantic import BaseModel
from app.database.tables.audit_logs import ActionType

class AuditLogBase(BaseModel):
    uid: uuid.UUID
    order_id: uuid.UUID | None = None
    cid: uuid.UUID | None = None
    action_type: ActionType | None = None
    details: str | None = None
    human_handoff: bool = False

class AuditLogCreate(AuditLogBase):
    pass

class AuditLogResponse(AuditLogBase):
    audit_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
