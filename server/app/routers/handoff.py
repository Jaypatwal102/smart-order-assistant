from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.conversations import FallbackHandoff, Conversation, Message
from app.models.users import User, UserSession
import json
import uuid
from typing import Dict, Optional

router = APIRouter(prefix="/handoff", tags=["handoff"])

class ConnectionManager:
    def __init__(self):
        # Maps user session_id (or conversation_id) to WebSocket
        self.user_connections: Dict[str, WebSocket] = {}
        # Maps agent user_id to WebSocket
        self.agent_connections: Dict[str, WebSocket] = {}
        # Simple queue for handoffs (list of conversation_ids)
        self.queue: list[str] = []

    async def connect_user(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        self.user_connections[conversation_id] = websocket
        if conversation_id not in self.queue:
            self.queue.append(conversation_id)
            await self.broadcast_to_agents({"type": "queue_update", "queue_size": len(self.queue)})

    def disconnect_user(self, conversation_id: str):
        if conversation_id in self.user_connections:
            del self.user_connections[conversation_id]
        if conversation_id in self.queue:
            self.queue.remove(conversation_id)

    async def connect_agent(self, websocket: WebSocket, agent_id: str):
        await websocket.accept()
        self.agent_connections[agent_id] = websocket
        # Send current queue size on connect
        await websocket.send_json({"type": "queue_update", "queue_size": len(self.queue)})

    def disconnect_agent(self, agent_id: str):
        if agent_id in self.agent_connections:
            del self.agent_connections[agent_id]

    async def send_to_user(self, conversation_id: str, data: dict):
        if conversation_id in self.user_connections:
            await self.user_connections[conversation_id].send_json(data)

    async def send_to_agent(self, agent_id: str, data: dict):
        if agent_id in self.agent_connections:
            await self.agent_connections[agent_id].send_json(data)
            
    async def broadcast_to_agents(self, data: dict):
        for ws in self.agent_connections.values():
            await ws.send_json(data)

manager = ConnectionManager()

@router.websocket("/ws/user/{conversation_id}")
async def user_websocket(websocket: WebSocket, conversation_id: str, db: Session = Depends(get_db)):
    await manager.connect_user(websocket, conversation_id)
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
                        "conversation_id": conversation_id
                    })
            elif message_data.get("type") == "chat_message":
                # Save user message to DB
                db_msg = Message(
                    conversation_id=conversation_id,
                    sender_type="user",
                    message_text=message_data.get("message", "")
                )
                db.add(db_msg)
                db.commit()
                # Relay directly via WS if needed, though WebRTC datachannel might handle it
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await manager.send_to_agent(agent_id, message_data)

    except WebSocketDisconnect:
        manager.disconnect_user(conversation_id)
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
                    conversation_id = manager.queue.pop(0)
                    # Assign to agent in DB
                    handoff = db.query(FallbackHandoff).filter(
                        FallbackHandoff.conversation_id == conversation_id,
                        FallbackHandoff.assigned_agent_id.is_(None)
                    ).first()
                    if handoff:
                        handoff.assigned_agent_id = agent_id
                        db.commit()
                    
                    await manager.send_to_agent(agent_id, {
                        "type": "assigned",
                        "conversation_id": conversation_id
                    })
                    await manager.send_to_user(conversation_id, {
                        "type": "agent_assigned",
                        "agent_id": agent_id
                    })
                    await manager.broadcast_to_agents({"type": "queue_update", "queue_size": len(manager.queue)})

            elif message_data.get("type") in ["offer", "answer", "ice-candidate"]:
                conversation_id = message_data.get("conversation_id")
                if conversation_id:
                    await manager.send_to_user(conversation_id, {
                        "type": message_data["type"],
                        "payload": message_data.get("payload"),
                        "agent_id": agent_id
                    })
            elif message_data.get("type") == "chat_message":
                conversation_id = message_data.get("conversation_id")
                if conversation_id:
                    db_msg = Message(
                        conversation_id=conversation_id,
                        sender_type="human_agent",
                        message_text=message_data.get("message", "")
                    )
                    db.add(db_msg)
                    db.commit()
                    await manager.send_to_user(conversation_id, message_data)

    except WebSocketDisconnect:
        manager.disconnect_agent(agent_id)

@router.get("/queue/status")
def get_queue_status():
    return {"queue_size": len(manager.queue)}
