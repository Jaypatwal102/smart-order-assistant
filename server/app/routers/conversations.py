from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
import uuid
import os
import shutil
import whisper
from typing import Optional
import requests

from app.core.database import get_db
from app.core.config import RASA_URL
from app.models.users import User, UserSession
from app.models.conversations import Conversation, Message
from app.schemas.conversations import MessageCreate, ConversationUpdate
from app.routers.auth import get_current_user, oauth2_scheme

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

def _classify_message(message_text: str, conversation_id: str = None, user_id: str = None) -> dict:
    try:
        payload = {"message": message_text, "conversation_id": conversation_id}
        if user_id:
            payload["user_id"] = user_id
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

def _is_rasa_active(conversation_id: str) -> bool:
    try:
        tracker_url = f"{RASA_URL}/conversations/{conversation_id}/tracker"
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

def _forward_message_to_rasa(conversation_id: str, user_id: str, message_text: str, db: Session, target_language: str = "English"):
    bot_responses = []
    request_failed = False
    try:
        # 1. Sync the user_id slot in Rasa for this conversation session
        event_url = f"{RASA_URL}/conversations/{conversation_id}/tracker/events"
        requests.post(
            event_url,
            json={
                "event": "slot",
                "name": "user_id",
                "value": str(user_id)
            },
            timeout=5
        )
        
        # Translate message to English for Rasa NLU if user's language is not English
        rasa_message = message_text
        if target_language and target_language.lower() not in ["en", "english"]:
            # Only translate if it's not a slash command / intent payload (starts with /)
            if not message_text.startswith("/"):
                rasa_message = _translate_text(message_text, "English", source_language=target_language)
                
        # 2. Post the user message to Rasa REST webhook
        webhook_url = f"{RASA_URL}/webhooks/rest/webhook"
        rasa_res = requests.post(
            webhook_url,
            json={
                "sender": str(conversation_id),
                "message": rasa_message
            },
            timeout=10
        )
        
        if rasa_res.status_code == 200:
            bot_responses = rasa_res.json()
        else:
            request_failed = True
    except Exception as e:
        print(f"Rasa integration communication error: {e}. Falling back to default message.")
        request_failed = True

    if request_failed:
        # Fallback if Rasa is offline or threw an error
        fallback_text = _translate_text("I'm sorry, I am currently offline or experiencing issues. Please try again later.", target_language)
        ai_msg = Message(
            conversation_id=conversation_id,
            sender_type="bot",
            message_text=fallback_text
        )
        db.add(ai_msg)
    elif bot_responses:
        for resp in bot_responses:
            text_response = resp.get("text")
            if text_response:
                translated_text = _translate_text(text_response, target_language)
                ai_msg = Message(
                    conversation_id=conversation_id,
                    sender_type="bot",
                    message_text=translated_text
                )
                db.add(ai_msg)
    else:
        # Fallback if Rasa is online but didn't return a text response
        fallback_text = _translate_text("I'm sorry, I didn't quite catch that. Could you please rephrase?", target_language)
        ai_msg = Message(
            conversation_id=conversation_id,
            sender_type="bot",
            message_text=fallback_text
        )
        db.add(ai_msg)

router = APIRouter(prefix="/conversations", tags=["conversations"])



try:
    whisper_model = whisper.load_model("base")
except Exception as e:
    print(f"Warning: Could not load whisper model: {e}")
    whisper_model = None


@router.post("/message")
def send_message(
    msg_in: MessageCreate, 
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    # Find the active session using the token
    session = db.query(UserSession).filter(UserSession.auth_token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Determine conversation_id
    conversation_id = msg_in.conversation_id
    if not conversation_id:
        # Create a new conversation
        conv = Conversation(
            session_id=session.session_id,
            status="active"
        )
        db.add(conv)
        db.flush()  # To get the conversation_id
        conversation_id = conv.conversation_id
    else:
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
            
        conv = db.query(Conversation).filter(Conversation.conversation_id == conv_uuid).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Create User Message
    user_msg = Message(
        conversation_id=conversation_id,
        sender_type="user",
        message_text=msg_in.message_text
    )
    db.add(user_msg)
    
    if _is_rasa_active(str(conversation_id)):
        _forward_message_to_rasa(str(conversation_id), str(current_user.user_id), msg_in.message_text, db, conv.detected_language)
    else:
        # Classify message intent first
        classification = _classify_message(msg_in.message_text, str(conversation_id), str(current_user.user_id))
        intent = classification.get("intent")
        detected_language = classification.get("language", "English")
        
        if detected_language.lower() not in ["en", "english"]:
            conv.detected_language = detected_language
            
        sub_intents_str = ", ".join(classification.get("sub_intents", [])) or "None"
        
        if intent == "shipping_address_update":
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            _forward_message_to_rasa(str(conversation_id), str(current_user.user_id), "/shipping_address_update", db, conv.detected_language)
        elif intent == "greeting":
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            
            translated_greeting = _translate_text("Hello! How can I help you today?", conv.detected_language)
            bot_msg = Message(
                conversation_id=conversation_id,
                sender_type="bot",
                message_text=translated_greeting
            )
            db.add(bot_msg)
        elif intent == "order_issue" and "cancel_product" in classification.get("sub_intents", []):
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            bot_reply = classification.get("bot_response")
            if bot_reply:
                translated_reply = _translate_text(bot_reply, conv.detected_language)
                db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=translated_reply))
        else:
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            bot_reply = classification.get("bot_response")
            if bot_reply:
                translated_reply = _translate_text(bot_reply, conv.detected_language)
                db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=translated_reply))
            db.commit()
            return classification
        
    db.commit()
    
    # Refresh to load messages
    conv = db.query(Conversation).options(joinedload(Conversation.messages)).filter(Conversation.conversation_id == conversation_id).first()
    
    msgs = []
    for m in conv.messages:
        msgs.append({
            "id": str(m.message_id),
            "sender_type": m.sender_type,
            "message_text": m.message_text,
            "audio_url": m.audio_url,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    msgs.sort(key=lambda x: x["created_at"] or "")
    
    return {
        "id": str(conv.conversation_id),
        "status": conv.status,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
        "messages": msgs
    }

@router.post("/audio")
def send_audio(
    audio: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    session = db.query(UserSession).filter(UserSession.auth_token == token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if not conversation_id or conversation_id == "null":
        conv = Conversation(session_id=session.session_id, status="active")
        db.add(conv)
        db.flush()
        conversation_id = str(conv.conversation_id)
    else:
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
            
        conv = db.query(Conversation).filter(Conversation.conversation_id == conv_uuid).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Save audio file
    file_ext = audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "webm"
    audio_filename = f"{uuid.uuid4()}.{file_ext}"
    audio_path = os.path.abspath(os.path.join("audios", audio_filename))
    
    with open(audio_path, "wb") as f:
        f.write(audio.file.read())
        
    transcribed_text = "Audio message received (Transcription unavailable)"
    detected_lang = "en"
    
    if whisper_model:
        if not shutil.which("ffmpeg"):
            print("ERROR: ffmpeg is not installed or not in PATH. Whisper requires ffmpeg.")
            transcribed_text = "Audio received but could not be transcribed (ffmpeg missing on server)."
        else:
            try:
                result = whisper_model.transcribe(audio_path)
                transcribed_text = result.get("text", "").strip()
                detected_lang = result.get("language", "en")
                conv.detected_language = detected_lang
                db.add(conv)
            except Exception as e:
                print(f"Error transcribing: {e}")

    user_msg = Message(
        conversation_id=conversation_id,
        sender_type="user",
        message_text=transcribed_text,
        audio_url=f"/audios/{audio_filename}",
        input_language=detected_lang
    )
    db.add(user_msg)
    
    if _is_rasa_active(str(conversation_id)):
        _forward_message_to_rasa(str(conversation_id), str(current_user.user_id), transcribed_text, db, conv.detected_language)
    else:
        # Classify message intent first
        classification = _classify_message(transcribed_text, str(conversation_id), str(current_user.user_id))
        intent = classification.get("intent")
        detected_language = classification.get("language", "English")
        
        if detected_language.lower() not in ["en", "english"]:
            conv.detected_language = detected_language
            
        sub_intents_str = ", ".join(classification.get("sub_intents", [])) or "None"
        
        if intent == "shipping_address_update":
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            _forward_message_to_rasa(str(conversation_id), str(current_user.user_id), "/shipping_address_update", db, conv.detected_language)
        elif intent == "greeting":
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            
            translated_greeting = _translate_text("Hello! How can I help you today?", conv.detected_language)
            bot_msg = Message(
                conversation_id=conversation_id,
                sender_type="bot",
                message_text=translated_greeting
            )
            db.add(bot_msg)
        elif intent == "order_issue" and "cancel_product" in classification.get("sub_intents", []):
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            bot_reply = classification.get("bot_response")
            if bot_reply:
                translated_reply = _translate_text(bot_reply, conv.detected_language)
                db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=translated_reply))
        else:
            db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=f"[Classification Debug] Intent: {intent} | Sub-intents: {sub_intents_str} | Confidence: {classification.get('confidence')}% | Lang: {detected_language}"))
            bot_reply = classification.get("bot_response")
            if bot_reply:
                translated_reply = _translate_text(bot_reply, conv.detected_language)
                db.add(Message(conversation_id=conversation_id, sender_type="bot", message_text=translated_reply))
            db.commit()
            return classification
    
    db.commit()
    
    conv = db.query(Conversation).options(joinedload(Conversation.messages)).filter(Conversation.conversation_id == conversation_id).first()
    
    msgs = []
    for m in conv.messages:
        msgs.append({
            "id": str(m.message_id),
            "sender_type": m.sender_type,
            "message_text": m.message_text,
            "audio_url": m.audio_url,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    msgs.sort(key=lambda x: x["created_at"] or "")
    
    return {
        "id": str(conv.conversation_id),
        "status": conv.status,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
        "messages": msgs
    }


@router.get("")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all conversations belonging to the user's active sessions."""
    sessions = db.query(UserSession).filter(UserSession.user_id == current_user.user_id).all()
    session_ids = [s.session_id for s in sessions]
    
    if not session_ids:
        return []
        
    conversations = (
        db.query(Conversation)
        .filter(Conversation.session_id.in_(session_ids))
        .order_by(Conversation.started_at.desc())
        .all()
    )
    
    return [
        {
            "id": str(c.conversation_id),
            "status": c.status,
            "detected_language": c.detected_language,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None
        }
        for c in conversations
    ]


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches full details and message history of a specific conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format."
        )

    conv = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.conversation_id == conv_uuid)
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found."
        )
        
    # Verify access permission (must belong to one of current user's sessions)
    session = db.query(UserSession).filter(UserSession.session_id == conv.session_id).first()
    if not session or session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this conversation is denied."
        )

    msgs = [
        {
            "id": str(m.message_id),
            "sender_type": m.sender_type,
            "message_text": m.message_text,
            "audio_url": m.audio_url,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in conv.messages
    ]
    msgs.sort(key=lambda x: x["created_at"] or "")

    return {
        "id": str(conv.conversation_id),
        "status": conv.status,
        "detected_language": conv.detected_language,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
        "messages": msgs
    }


@router.put("/{conversation_id}")
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates status or metadata for a specific conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format."
        )

    conv = db.query(Conversation).filter(Conversation.conversation_id == conv_uuid).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found."
        )
        
    # Verify access permission
    session = db.query(UserSession).filter(UserSession.session_id == conv.session_id).first()
    if not session or session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this conversation is denied."
        )

    if payload.status is not None:
        if payload.status not in ["active", "completed", "handed_over"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation status. Must be 'active', 'completed', or 'handed_over'."
            )
        conv.status = payload.status
        if payload.status == "completed":
            conv.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
    if payload.detected_language is not None:
        conv.detected_language = payload.detected_language

    db.commit()
    db.refresh(conv)

    return {
        "id": str(conv.conversation_id),
        "status": conv.status,
        "detected_language": conv.detected_language,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "ended_at": conv.ended_at.isoformat() if conv.ended_at else None
    }
