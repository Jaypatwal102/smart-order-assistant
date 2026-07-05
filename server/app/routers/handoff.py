from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.tables.conversations import Conversation
from app.database.tables.messages import Message, SenderType
from app.database.tables.audit_logs import AuditLog
from app.database.tables.users import User
import json
import uuid
from typing import Dict, Optional

router = APIRouter(prefix="/handoff", tags=["handoff"])

class ConnectionManager:
    def __init__(self):
        # Maps user cid to WebSocket
        self.user_connections: Dict[str, WebSocket] = {}
        # Maps agent uid to WebSocket
        self.agent_connections: Dict[str, WebSocket] = {}
        # Simple queue for handoffs (list of cid)
        self.queue: list[str] = []

    async def connect_user(self, websocket: WebSocket, cid: str):
        await websocket.accept()
        self.user_connections[cid] = websocket
        if cid not in self.queue:
            self.queue.append(cid)
            await self.broadcast_to_agents({"type": "queue_update", "queue_size": len(self.queue)})

    def disconnect_user(self, cid: str):
        if cid in self.user_connections:
            del self.user_connections[cid]
        if cid in self.queue:
            self.queue.remove(cid)

    async def connect_agent(self, websocket: WebSocket, agent_id: str):
        await websocket.accept()
        self.agent_connections[agent_id] = websocket
        # Send current queue size on connect
        await websocket.send_json({"type": "queue_update", "queue_size": len(self.queue)})

    def disconnect_agent(self, agent_id: str):
        if agent_id in self.agent_connections:
            del self.agent_connections[agent_id]

    async def send_to_user(self, cid: str, data: dict):
        if cid in self.user_connections:
            await self.user_connections[cid].send_json(data)

    async def send_to_agent(self, agent_id: str, data: dict):
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].send_json(data)
            
    async def broadcast_to_agents(self, data: dict):
        for ws in self.agent_connections.values():
            await ws.send_json(data)

manager = ConnectionManager()

@router.websocket("/ws/user/{cid}")
async def user_websocket(websocket: WebSocket, cid: str, db: Session = Depends(get_db)):
    await manager.connect_user(websocket, cid)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle WebRTC signaling or messages
            if message_data.get("type") in ["offer", "answer", "ice-candidate"]:
                # Relay to assigned agent
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await manager.send_to_agent(agent_id, {
                        "type": message_data["type"],
                        "payload": message_data.get("payload"),
                        "cid": cid
                    })
            elif message_data.get("type") == "chat_message":
                # Save user message to DB
                db_msg = Message(
                    cid=uuid.UUID(cid),
                    sender_type=SenderType.USER,
                    message_text=message_data.get("message", "")
                )
                db.add(db_msg)
                db.commit()
                
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await manager.send_to_agent(agent_id, message_data)

    except WebSocketDisconnect:
        manager.disconnect_user(cid)
        await manager.broadcast_to_agents({"type": "queue_update", "queue_size": len(manager.queue)})

@router.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str, db: Session = Depends(get_db)):
    await manager.connect_agent(websocket, agent_id)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "accept_next":
                if manager.queue:
                    cid = manager.queue.pop(0)
                    
                    # Log the handoff in AuditLog
                    conv = db.query(Conversation).filter(Conversation.cid == uuid.UUID(cid)).first()
                    if conv:
                        audit_log = AuditLog(
                            uid=conv.uid,
                            cid=conv.cid,
                            details=f"Human handoff accepted by agent {agent_id}",
                            human_handoff=True
                        )
                        db.add(audit_log)
                        db.commit()
                    
                    await manager.send_to_agent(agent_id, {
                        "type": "assigned",
                        "cid": cid
                    })
                    await manager.send_to_user(cid, {
                        "type": "agent_assigned",
                        "agent_id": agent_id
                    })
                    await manager.broadcast_to_agents({"type": "queue_update", "queue_size": len(manager.queue)})

            elif message_data.get("type") in ["offer", "answer", "ice-candidate", "end_chat"]:
                cid = message_data.get("cid") or message_data.get("conversation_id")
                if cid:
                    await manager.send_to_user(cid, {
                        "type": message_data["type"],
                        "payload": message_data.get("payload"),
                        "agent_id": agent_id
                    })
            elif message_data.get("type") == "chat_message":
                cid = message_data.get("cid") or message_data.get("conversation_id")
                if cid:
                    db_msg = Message(
                        cid=uuid.UUID(cid),
                        sender_type=SenderType.HUMAN_AGENT,
                        message_text=message_data.get("message", "")
                    )
                    db.add(db_msg)
                    db.commit()
                    await manager.send_to_user(cid, message_data)

    except WebSocketDisconnect:
        manager.disconnect_agent(agent_id)

@router.get("/queue/status")
def get_queue_status():
    return {"queue_size": len(manager.queue)}
