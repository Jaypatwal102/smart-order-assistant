from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
import uuid
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.users import User, UserSession
from app.models.conversations import Conversation, Message
from app.schemas.auth import UserCreate, UserLogin, Token, UserResponse
from app.utils.password import get_password_hash, verify_password
from app.utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.user_id == uuid.UUID(user_id)).first()
    if user is None:
        raise credentials_exception
        
    session = db.query(UserSession).filter(UserSession.auth_token == token).first()
    if not session or session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise credentials_exception
        
    return user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES or 30))
    access_token = create_access_token(
        data={"sub": str(user.user_id)}, expires_delta=access_token_expires
    )
    
    expires_at = datetime.now() + access_token_expires
    user_session = UserSession(
        user_id=user.user_id,
        auth_token=access_token,
        expires_at=expires_at
    )
    db.add(user_session)
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Find User (already have current_user)
    # 2. Find Sessions
    sessions = db.query(UserSession).filter(UserSession.user_id == current_user.user_id).all()
    session_ids = [s.session_id for s in sessions]
    
    conv_list = []
    if session_ids:
        # 3. Find Conversations and 4. Messages (via joinedload)
        conversations = (
            db.query(Conversation)
            .options(joinedload(Conversation.messages))
            .filter(Conversation.session_id.in_(session_ids))
            .order_by(Conversation.started_at.desc())
            .all()
        )
        
        # 5. Build JSON
        for conv in conversations:
            msgs = []
            for msg in conv.messages:
                msgs.append({
                    "id": str(msg.message_id),
                    "sender_type": msg.sender_type,
                    "message_text": msg.message_text,
                    "audio_url": msg.audio_url,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                })
            
            # Sort messages by created_at ascending
            msgs.sort(key=lambda x: x["created_at"] or "")
            
            conv_list.append({
                "id": str(conv.conversation_id),
                "status": conv.status,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                "messages": msgs
            })
            
    # 6. Return to frontend
    user_data = {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "created_at": current_user.created_at,
        "conversations": conv_list
    }
    
    return user_data
