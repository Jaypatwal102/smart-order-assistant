import json
import logging
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Intent Classification Service")

OLLAMA_URL = "http://localhost:11434/api/generate"
#MODEL_NAME = "qwen3:4b"
MODEL_NAME = "gemma3:4b"

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    intent: str
    sub_intents: list[str]
    confidence: int
    language: str

class TranslateRequest(BaseModel):
    text: str
    target_language: str

class TranslateResponse(BaseModel):
    translated_text: str

SYSTEM_PROMPT = """You are an intent classification service for a customer support chatbot.
Analyze the user message and classify it into exactly one of these intents:
You need to multilingual support for languages English, French, Russian, Hindi.

- greeting (e.g. "hi", "hello", "good morning")
- shipping_address_update (e.g. "update my shipping address")
- order_issue (e.g. "received the wrong product", "recommend another product", "cancel my order")
- human_handoff (e.g. "connect me to an agent")
- unknown (if confidence is low or it does not match the above)

Supported sub-intents (only for order_issue):
- replace_product
- cancel_product
- product_recommendation

Rules:
- Extract all applicable sub-intents if there are multiple.
- Return ONLY a valid JSON object. Do not add any conversational text.
- IMPORTANT: Do NOT output any <think> tags. Do NOT provide any step-by-step reasoning. Output the JSON immediately.

Examples:
User: "hello"
{"intent": "greeting", "sub_intents": [], "confidence": 99, "language": "English"}

User: "I want to change my delivery address"
{"intent": "shipping_address_update", "sub_intents": [], "confidence": 95, "language": "English"}

User: "cancel my moisturizer"
{"intent": "order_issue", "sub_intents": ["cancel_product"], "confidence": 90, "language": "English"}

User: "my lotion arrived broken, I want to cancel it and can you suggest another one?"
{"intent": "order_issue", "sub_intents": ["cancel_product", "product_recommendation"], "confidence": 92, "language": "English"}

User: "I want to talk to a human"
{"intent": "human_handoff", "sub_intents": [], "confidence": 100, "language": "English"}

User: "Bonjour, j'ai reçu le mauvais produit"
{"intent": "order_issue", "sub_intents": ["replace_product"], "confidence": 95, "language": "French"}
"""

@app.get("/debug_chat")
async def debug_chat(msg: str):
    payload = {
        "model": MODEL_NAME,
        "prompt": msg,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
            return response.json()
        except Exception as e:
            logger.error(f"Debug chat error: {e}")
            return {"error": str(e)}

@app.post("/chat", response_model=ChatResponse)
async def classify_intent(request: ChatRequest):
    payload = {
        "model": MODEL_NAME,
        "prompt": request.message,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
            response.raise_for_status()
            
            data = response.json()
            response_text = data.get("response", "").strip()
            
            # Clean up potential markdown formatting and conversational text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            else:
                response_text = ""
                
            if not response_text:
                logger.error(f"Ollama returned empty response. Raw data: {data}")
                return ChatResponse(intent="unknown", sub_intents=[], confidence=0, language="English")
            
            # Parse the JSON response
            try:
                parsed_json = json.loads(response_text)
                
                # Enforce schema structure
                intent = parsed_json.get("intent", "unknown")
                sub_intents = parsed_json.get("sub_intents", [])
                confidence = parsed_json.get("confidence", 0)
                language = parsed_json.get("language", "English")
                
                if not isinstance(sub_intents, list):
                    sub_intents = []
                if not isinstance(confidence, int):
                    try:
                        confidence = int(confidence)
                    except ValueError:
                        confidence = 0
                
                if confidence < 50:
                    intent = "unknown"
                    
                return ChatResponse(
                    intent=intent,
                    sub_intents=sub_intents,
                    confidence=confidence,
                    language=language
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Ollama: {response_text}. Error: {e}")
                raise HTTPException(status_code=500, detail="Invalid JSON format returned by LLM")
                
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Ollama: {e}")
        raise HTTPException(status_code=503, detail="Ollama service unavailable")
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama returned an error status: {e}")
        raise HTTPException(status_code=502, detail="Error returned by Ollama service")

@app.post("/translate", response_model=TranslateResponse)
async def translate_text(request: TranslateRequest):
    if request.target_language.lower() in ["en", "english"]:
        return TranslateResponse(translated_text=request.text)
        
    prompt = f"Translate the following text to {request.target_language}. Do not output any thinking tags. Do not explain anything. Just output the precise translated text and nothing else.\n\nText: {request.text}"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=120.0)
            response.raise_for_status()
            
            data = response.json()
            translated = data.get("response", "").strip()
            
            # Clean up potential markdown formatting and tags
            translated = re.sub(r'<think>.*?</think>', '', translated, flags=re.DOTALL).strip()
            
            if not translated:
                translated = request.text
                
            return TranslateResponse(translated_text=translated)
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return TranslateResponse(translated_text=request.text)

@app.get("/health")
def health_check():
    return {"status": "ok"}
