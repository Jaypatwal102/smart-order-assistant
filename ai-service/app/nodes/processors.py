import re
import logging
import requests
from app.llm.ollama import get_llm
from app.models.state import AgentState, ExtractionResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract any customer entities from the user message.
Specifically look for:
- order_id: A 36-character UUID string (e.g., '12345678-1234-1234-1234-123456789012')
- new_address: A new shipping/delivery address description.

If any entity is not present, return null for it.
"""

def process_shipping_update(state: AgentState) -> dict:
    return {"bot_response": "Shipping address update should be handled by Rasa."}

def process_greeting(state: AgentState) -> dict:
    return {"bot_response": "Hello! How can I help you today?"}

def process_order_issue(state: AgentState) -> dict:
    if "cancel_product" not in state.get("sub_intents", []):
        return {"bot_response": "I'm sorry, I can only help with cancelling products right now."}
        
    order_id = state.get("order_id")
    message = state.get("message", "")
    
    if not order_id:
        match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', message)
        if match:
            order_id = match.group(0)
        else:
            try:
                llm = get_llm()
                parser = JsonOutputParser(pydantic_object=ExtractionResult)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", EXTRACTION_PROMPT + "\n\n{format_instructions}"),
                    ("user", "{message}")
                ])
                chain = prompt | llm | parser
                res = chain.invoke({
                    "message": message,
                    "format_instructions": parser.get_format_instructions()
                })
                order_id = res.get("order_id")
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                
    if not order_id:
        return {"bot_response": "Please provide your exact order ID to proceed with cancellation."}
        
    user_id = state.get("user_id")
    if not user_id:
        return {"order_id": order_id, "bot_response": "Session error: user ID is missing. Please log in again."}
        
    try:
        url = f"http://localhost:8000/orders/{order_id}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 404:
            return {"order_id": None, "bot_response": f"Sorry, no order was found with ID '{order_id}'. Please try again."}
        elif resp.status_code != 200:
            return {"order_id": None, "bot_response": "Error validating your order. Please try again later."}
            
        order_data = resp.json()
        
        if str(order_data.get("user_id")).lower() != str(user_id).lower():
            return {"order_id": None, "bot_response": f"Sorry, order '{order_id}' is not associated with your account.", "intent": "completed", "sub_intents": []}
            
        cancel_url = f"http://localhost:8000/orders/{order_id}/cancel"
        cancel_resp = requests.put(cancel_url, timeout=5)
        
        if cancel_resp.status_code == 200:
            return {"order_id": order_id, "bot_response": f"Your order '{order_id}' has been successfully cancelled.", "intent": "completed", "sub_intents": []}
        else:
            error_detail = cancel_resp.json().get("detail", "Unknown error")
            return {"order_id": None, "bot_response": f"Failed to cancel order: {error_detail}", "intent": "completed", "sub_intents": []}
            
    except Exception as e:
        logger.error(f"Order cancellation API error: {e}")
        return {"order_id": order_id, "bot_response": "Error contacting the server for cancellation. Please try again later."}

def process_default(state: AgentState) -> dict:
    return {"bot_response": "I didn't quite catch that. Could you please rephrase?"}
