import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.graphs.intent_classifier import intent_classifier_graph
from app.services.translator import translate_text_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Intent Classification Service")

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    cid: Optional[str] = None
    user_id: Optional[str] = None
    uid: Optional[str] = None

class ChatResponse(BaseModel):
    intent: str
    sub_intents: list[str]
    confidence: int
    language: str
    order_id: Optional[str] = None
    new_address: Optional[str] = None
    bot_response: Optional[str] = None
    handoff_required: bool = False
    handoff_reason: Optional[str] = None

class TranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: Optional[str] = None

class TranslateResponse(BaseModel):
    translated_text: str

@app.post("/chat", response_model=ChatResponse)
async def classify_intent(request: ChatRequest):
    try:
        thread_id = request.conversation_id or request.cid or "default"
        config = {"configurable": {"thread_id": thread_id}}
        
        effective_user_id = request.user_id or request.uid
        
        # Invoke the graph with thread-based memory checkpointing
        result = await intent_classifier_graph.ainvoke(
            {
                "message": request.message,
                "conversation_id": thread_id,
                "user_id": effective_user_id
            },
            config=config
        )
        
        return ChatResponse(
            intent=result.get("intent", "unknown"),
            sub_intents=result.get("sub_intents", []),
            confidence=result.get("confidence", 0),
            language=result.get("language", "English"),
            order_id=result.get("order_id"),
            new_address=result.get("new_address"),
            bot_response=result.get("bot_response"),
            handoff_required=result.get("handoff_required", False),
            handoff_reason=result.get("handoff_reason")
        )
    except Exception as e:
        logger.error(f"Error during graph classification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate", response_model=TranslateResponse)
async def translate_text_endpoint(request: TranslateRequest):
    try:
        translated_text = await translate_text_service(request.text, request.target_language, request.source_language)
        return TranslateResponse(translated_text=translated_text)
    except Exception as e:
        logger.error(f"Error during translation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
