from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
import uuid
import os
import shutil
import whisper
from typing import Optional
from app.core.database import get_db
from app.models.users import User, UserSession
from app.models.conversations import Conversation, Message
from app.schemas.conversations import MessageCreate
from app.routers.auth import get_current_user, oauth2_scheme

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
    
    # Create Mock AI Message
    ai_msg = Message(
        conversation_id=conversation_id,
        sender_type="bot",
        message_text="I have received your message. I am an AI assistant and will process your request shortly."
    )
    db.add(ai_msg)
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
    
    ai_msg = Message(
        conversation_id=conversation_id,
        sender_type="bot",
        message_text=f"I heard you say: '{transcribed_text}'. I am an AI assistant and will process your request shortly."
    )
    db.add(ai_msg)
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
