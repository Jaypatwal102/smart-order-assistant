from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
import uuid
import os
import shutil
import whisper
from typing import Optional
import requests

from app.database.connection import get_db
from app.config import RASA_URL
from app.database.tables.users import User
from app.database.tables.conversations import Conversation, ConversationStatus
from app.database.tables.messages import Message, SenderType
from app.database.data_types.conversations import ConversationCreate, ConversationResponse
from app.database.data_types.messages import MessageCreate, MessageResponse
from app.routers.auth import get_current_user

def _translate_text(text: str, target_language: str, source_language: Optional[str] = None) -> str:
    if not target_language:
        return text
    if source_language and target_language.lower() == source_language.lower():
        return text
    if target_language.lower() in ["en", "english"] and (source_language is None or source_language.lower() in ["en", "english"]):
        return text
    try:
        payload = {"text": text, "target_language": target_language}
        if source_language:
            payload["source_language"] = source_language
        ai_res = requests.post(
            "http://localhost:8001/translate",
            json=payload,
            timeout=120
        )
        if ai_res.status_code == 200:
            return ai_res.json().get("translated_text", text)
    except Exception as e:
        print(f"AI Service translation error: {e}")
    return text

def _classify_message(message_text: str, cid: str | None = None, uid: str | None = None) -> dict:
    try:
        payload = {"message": message_text, "conversation_id": cid}
        if uid:
            payload["user_id"] = uid
        ai_res = requests.post(
            "http://localhost:8001/chat",
            json=payload,
            timeout=120
        )
        if ai_res.status_code == 200:
            return ai_res.json()
    except Exception as e:
        print(f"AI Service communication error: {e}")
    return {"intent": "unknown", "sub_intents": [], "confidence": 0}

def _is_rasa_active(cid: str) -> bool:
    try:
        tracker_url = f"{RASA_URL}/conversations/{cid}/tracker"
        res = requests.get(tracker_url, timeout=5)
        if res.status_code == 200:
            tracker = res.json()
            if tracker.get("active_loop", {}).get("name"):
                return True
            for event in reversed(tracker.get("events", [])):
                if event.get("event") == "action" and event.get("name") != "action_listen":
                    if event.get("name") in ["utter_confirm_update", "shipping_address_update_form"]:
                        return True
                    break
    except Exception as e:
        print(f"Failed to fetch Rasa tracker: {e}")
    return False

def _forward_message_to_rasa(cid: str, uid: str, message_text: str, db: Session, target_language: str = "English"):
    bot_responses = []
    request_failed = False
    try:
        event_url = f"{RASA_URL}/conversations/{cid}/tracker/events"
        requests.post(event_url, json={"event": "slot", "name": "user_id", "value": str(uid)}, timeout=5)
        
        rasa_message = message_text
        if target_language and target_language.lower() not in ["en", "english"]:
            if not message_text.startswith("/"):
                rasa_message = _translate_text(message_text, "English", source_language=target_language)
                
        webhook_url = f"{RASA_URL}/webhooks/rest/webhook"
        rasa_res = requests.post(webhook_url, json={"sender": str(cid), "message": rasa_message}, timeout=10)
        
        if rasa_res.status_code == 200:
            bot_responses = rasa_res.json()
        else:
            request_failed = True
    except Exception as e:
        print(f"Rasa integration communication error: {e}")
        request_failed = True

    if request_failed:
        fallback_text = _translate_text("I'm sorry, I am currently offline.", target_language)
        db.add(Message(cid=uuid.UUID(cid), sender_type=SenderType.BOT, message_text=fallback_text))
    elif bot_responses:
        for resp in bot_responses:
            text_response = resp.get("text")
            if text_response:
                translated_text = _translate_text(text_response, target_language)
                db.add(Message(cid=uuid.UUID(cid), sender_type=SenderType.BOT, message_text=translated_text))
    else:
        fallback_text = _translate_text("I'm sorry, I didn't quite catch that.", target_language)
        db.add(Message(cid=uuid.UUID(cid), sender_type=SenderType.BOT, message_text=fallback_text))

router = APIRouter(prefix="/conversations", tags=["conversations"])

try:
    whisper_model = whisper.load_model("base")
except Exception as e:
    print(f"Warning: Could not load whisper model: {e}")
    whisper_model = None

from pydantic import BaseModel
class MsgInput(BaseModel):
    cid: str | None = None
    message_text: str

@router.post("/message")
def send_message(
    msg_in: MsgInput, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cid = msg_in.cid
    if not cid:
        conv = Conversation(uid=current_user.uid, status=ConversationStatus.ACTIVE)
        db.add(conv)
        db.flush()
        cid = str(conv.cid)
    else:
        try:
            conv_uuid = uuid.UUID(cid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cid format")
            
        conv = db.query(Conversation).filter(Conversation.cid == conv_uuid).first()  # type: ignore
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    user_msg = Message(cid=uuid.UUID(cid), sender_type=SenderType.USER, message_text=msg_in.message_text)
    db.add(user_msg)
    
    if _is_rasa_active(str(cid)):
        _forward_message_to_rasa(str(cid), str(current_user.uid), msg_in.message_text, db)
    else:
        classification = _classify_message(msg_in.message_text, str(cid), str(current_user.uid))
        intent = classification.get("intent")
        
        bot_reply = classification.get("bot_response") or f"Acknowledged intent: {intent}"
        db.add(Message(cid=uuid.UUID(cid), sender_type=SenderType.BOT, message_text=bot_reply))
        
    db.commit()
    
    conv = db.query(Conversation).options(joinedload(Conversation.messages)).filter(Conversation.cid == uuid.UUID(cid)).first()  # type: ignore
    
    msgs = []
    for m in conv.messages:
        msgs.append({
            "mid": str(m.mid),
            "sender_type": m.sender_type.value if m.sender_type else None,
            "message_text": m.message_text,
            "audio_location": m.audio_location,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    msgs.sort(key=lambda x: x["created_at"] or "")
    
    return {
        "cid": str(conv.cid),
        "status": conv.status.value if conv.status else None,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "messages": msgs
    }

@router.post("/audio")
def send_audio(
    audio: UploadFile = File(...),
    cid: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not cid or cid == "null":
        conv = Conversation(uid=current_user.uid, status=ConversationStatus.ACTIVE)
        db.add(conv)
        db.flush()
        cid = str(conv.cid)
    else:
        try:
            conv_uuid = uuid.UUID(cid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cid format")
            
        conv = db.query(Conversation).filter(Conversation.cid == conv_uuid).first()  # type: ignore
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    file_ext = audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "webm"
    audio_filename = f"{uuid.uuid4()}.{file_ext}"
    audio_path = os.path.abspath(os.path.join("audios", audio_filename))
    
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    with open(audio_path, "wb") as f:
        f.write(audio.file.read())
        
    transcribed_text = "Audio message received"
    
    if whisper_model and shutil.which("ffmpeg"):
        try:
            result = whisper_model.transcribe(audio_path)
            transcribed_text = result.get("text", "").strip()
        except Exception as e:
            print(f"Error transcribing: {e}")

    user_msg = Message(
        cid=uuid.UUID(cid),
        sender_type=SenderType.USER,
        message_text=transcribed_text,
        audio_location=f"/audios/{audio_filename}"
    )
    db.add(user_msg)
    
    if _is_rasa_active(str(cid)):
        _forward_message_to_rasa(str(cid), str(current_user.uid), transcribed_text, db)
    else:
        classification = _classify_message(transcribed_text, str(cid), str(current_user.uid))
        intent = classification.get("intent")
        bot_reply = classification.get("bot_response") or f"Acknowledged intent: {intent}"
        db.add(Message(cid=uuid.UUID(cid), sender_type=SenderType.BOT, message_text=bot_reply))
        
    db.commit()
    
    conv = db.query(Conversation).options(joinedload(Conversation.messages)).filter(Conversation.cid == uuid.UUID(cid)).first()  # type: ignore
    
    msgs = []
    for m in conv.messages:
        msgs.append({
            "mid": str(m.mid),
            "sender_type": m.sender_type.value if m.sender_type else None,
            "message_text": m.message_text,
            "audio_location": m.audio_location,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    msgs.sort(key=lambda x: x["created_at"] or "")
    
    return {
        "cid": str(conv.cid),
        "status": conv.status.value if conv.status else None,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "messages": msgs
    }

@router.get("")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.uid == current_user.uid)
        .order_by(Conversation.started_at.desc())
        .all()
    )
    
    return [
        {
            "cid": str(c.cid),
            "status": c.status.value if c.status else None,
            "started_at": c.started_at.isoformat() if c.started_at else None
        }
        for c in conversations
    ]

@router.get("/{cid}")
def get_conversation(
    cid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        conv_uuid = uuid.UUID(cid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cid format.")

    conv = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.cid == conv_uuid)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
        
    if conv.uid != current_user.uid:
        raise HTTPException(status_code=403, detail="Access denied.")

    msgs = [
        {
            "mid": str(m.mid),
            "sender_type": m.sender_type.value if m.sender_type else None,
            "message_text": m.message_text,
            "audio_location": m.audio_location,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in conv.messages
    ]
    msgs.sort(key=lambda x: x["created_at"] or "")

    return {
        "cid": str(conv.cid),
        "status": conv.status.value if conv.status else None,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "messages": msgs
    }
