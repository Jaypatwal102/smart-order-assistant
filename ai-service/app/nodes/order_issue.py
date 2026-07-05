import re
import os
import logging
import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.llm.ollama import get_llm
from app.models.state import AgentState, ExtractionResult
from app.nodes.helpers import classify_response_to_offer, EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

def process_order_issue(state: AgentState) -> dict:
    order_id = state.get("order_id")
    message = state.get("message", "")
    
    # 1. Handle cancellation recommendations follow-up
    if state.get("cancel_offered"):
        recommended = state.get("recommended_products") or []
        res = classify_response_to_offer(message, "cancel_recommendations", recommended)
        decision = res.get("decision", "unknown")
        
        if decision == "check_recommendation" or decision == "accept_alternative":
            bot_msg = "Great! You can order it from here: http://example.com/order-alternative"
        else:
            bot_msg = "No problem! Let me know if you need help with anything else."
            
        return {
            "bot_response": bot_msg,
            "cancel_offered": False,
            "recommended_products": None,
            "intent": "completed",
            "sub_intents": []
        }
        
    sub_intents = state.get("sub_intents", [])
    
    # We support cancel_product in process_order_issue (replacement is now process_replacement)
    if "cancel_product" not in sub_intents:
        return {"bot_response": "I'm sorry, I can only help with cancelling products right now."}
        
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
        return {"bot_response": "Please provide your exact order ID to proceed with your request."}
        
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
            
        product_name = order_data.get("product_name")
        status = order_data.get("status", "")
        
        # Load cancellation policy
        policy_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "cancellation_policy.txt")
        with open(policy_path, "r") as f:
            cancellation_policy = f.read()
            
        # Cancellation policy checks
        if status.lower() == "delivered":
            return {
                "order_id": order_id,
                "bot_response": f"I'm sorry, I cannot cancel this order because it has already been delivered. The current status is '{status}'. Please request a replacement or refund.",
                "intent": "completed",
                "sub_intents": []
            }
        elif status.lower() == "dispatched":
            return {
                "order_id": order_id,
                "bot_response": f"Order '{order_id}' is already Dispatched.",
                "intent": "completed",
                "sub_intents": []
            }
        elif status.lower() == "cancelled":
            return {
                "order_id": order_id,
                "bot_response": f"Order '{order_id}' is already cancelled.",
                "intent": "completed",
                "sub_intents": []
            }
        elif status.lower() == "refunded":
            return {
                "order_id": order_id,
                "bot_response": f"Order '{order_id}' has already been refunded.",
                "intent": "completed",
                "sub_intents": []
            }
            
        # Process Cancellation
        cancel_url = f"http://localhost:8000/orders/{order_id}/cancel"
        cancel_resp = requests.put(cancel_url, timeout=5)
        
        if cancel_resp.status_code == 200:
            from app.services.recommendation import get_recommendations_service
            recs = get_recommendations_service(product_name, limit=2)
            
            bot_msg = f"Your order '{order_id}' for {product_name} has been successfully cancelled."
            if not recs:
                bot_msg += " Sorry, we didn't find any matching products for alternative recommendations."
                return {
                    "order_id": order_id,
                    "bot_response": bot_msg,
                    "cancel_offered": False,
                    "recommended_products": [],
                    "intent": "completed",
                    "sub_intents": []
                }
            
            if len(recs) == 1:
                alt1 = recs[0]["name"]
                bot_msg += f" If you are looking for an alternative, you might like our {alt1}. Would you like to check it out?"
            else:
                alt1 = recs[0]["name"]
                alt2 = recs[1]["name"]
                bot_msg += f" If you are looking for an alternative, you might like our {alt1} or {alt2}. Would you like to check either of these out?"
            
            return {
                "order_id": order_id,
                "bot_response": bot_msg,
                "cancel_offered": True,
                "recommended_products": recs,
                "intent": "completed",
                "sub_intents": []
            }
        else:
            error_detail = cancel_resp.json().get("detail", "Unknown error")
            return {"order_id": None, "bot_response": f"Failed to cancel order: {error_detail}", "intent": "completed", "sub_intents": []}
            
    except Exception as e:
        logger.error(f"Order issue API error: {e}")
        return {"order_id": order_id, "bot_response": "Error contacting the server. Please try again later."}
