from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta, timezone
import uuid
from jose import JWTError, jwt

from app.database.connection import get_db
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database.tables.users import User, UserRole
from app.database.tables.conversations import Conversation
from app.database.tables.messages import Message
from app.database.data_types.users import UserCreate, UserLogin, Token, UserResponse
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
        user_uid: str = payload.get("sub")
        if user_uid is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    try:
        uid = uuid.UUID(user_uid)
    except ValueError:
        raise credentials_exception

    user = db.query(User).filter(User.uid == uid).first()
    if user is None:
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
        hashed_password=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role or UserRole.USER
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES or 30))
    access_token = create_access_token(
        data={"sub": str(user.uid)}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.uid == current_user.uid)
        .order_by(Conversation.started_at.desc())
        .all()
    )
    
    conv_list = []
    for conv in conversations:
        msgs = []
        for msg in conv.messages:
            msgs.append({
                "mid": str(msg.mid),
                "sender_type": msg.sender_type.value if msg.sender_type else None,
                "message_text": msg.message_text,
                "audio_location": msg.audio_location,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })
            
        msgs.sort(key=lambda x: x["created_at"] or "")
        
        conv_list.append({
            "id": str(conv.cid),  # renamed to id for frontend compatibility or just cid
            "cid": str(conv.cid),
            "status": conv.status.value if conv.status else None,
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "messages": msgs
        })
        
    user_data = {
        "uid": str(current_user.uid),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value if current_user.role else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "conversations": conv_list
    }
    
    return user_data
