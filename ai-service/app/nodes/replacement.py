import re
import os
import logging
import requests
import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.llm.ollama import get_llm
from app.models.state import AgentState, ExtractionResult
from app.nodes.helpers import classify_response_to_offer, EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

def process_replacement(state: AgentState) -> dict:
    order_id = state.get("order_id")
    message = state.get("message", "")
    
    # 1. Handle replacement follow-up
    if state.get("replacement_offered"):
        recommended = state.get("recommended_products") or []
        res = classify_response_to_offer(message, "replacement_exchange", recommended)
        decision = res.get("decision", "unknown")
        chosen_product = res.get("chosen_product")
        
        if decision == "check_recommendation" or decision == "accept_alternative":
            bot_msg = "Great! You can order it from here: http://example.com/order-alternative"
            return {
                "bot_response": bot_msg,
                "replacement_offered": False,
                "recommended_products": None,
                "intent": "completed",
                "sub_intents": []
            }
        elif decision == "accept_same" or decision == "decline":
            # "in replacement say thankyou and reorder the same product"
            try:
                url = f"http://localhost:8000/orders/{order_id}"
                resp = requests.get(url, timeout=5)
                order_data = resp.json()
                product_name = order_data.get("product_name")
                
                replace_url = f"http://localhost:8000/orders/{order_id}/replace"
                replace_resp = requests.post(replace_url, json={}, timeout=5)
                if replace_resp.status_code == 200:
                    bot_msg = f"Thank you! I have processed a replacement for your **{product_name}**. A new order has been created."
                    return {
                        "bot_response": bot_msg,
                        "replacement_offered": False,
                        "recommended_products": None,
                        "intent": "completed",
                        "sub_intents": []
                    }
            except Exception as e:
                logger.error(f"Failed to process replacement: {e}")
                
            bot_msg = "There was an error processing your replacement. I will transfer you to a human agent."
            return {
                "bot_response": bot_msg,
                "handoff_required": True,
                "handoff_reason": "Replacement API failed",
                "replacement_offered": False,
                "recommended_products": None,
                "intent": "completed",
                "sub_intents": []
            }
        else:
            if recommended:
                bot_msg = "I didn't catch that. Would you like me to process a replacement for the same item, or would you prefer one of the alternatives?"
            else:
                bot_msg = "I didn't catch that. Would you like me to process a replacement for the same item?"
            return {"bot_response": bot_msg}

    # 2. Extract and validate Order ID
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
        return {"bot_response": "Please provide your exact order ID to proceed with your replacement."}
        
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
        
        # Load replacement policy
        policy_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "replacement_policy.txt")
        with open(policy_path, "r") as f:
            replacement_policy = f.read()
            
        # Replacement policy checks
        if status.lower() != "delivered":
            return {
                "order_id": order_id,
                "bot_response": f"I can only replace products that have already been delivered. The current status of this order is '{status}'.",
                "intent": "completed",
                "sub_intents": []
            }
            
        if order_data.get("delivered_at"):
            try:
                del_str = order_data.get('delivered_at').replace('Z', '')
                delivered_date = datetime.datetime.fromisoformat(del_str).replace(tzinfo=None)
                if (datetime.datetime.now() - delivered_date).days > 7:
                    return {
                        "order_id": order_id,
                        "bot_response": "I'm sorry, but this order is outside our 7-day replacement window. I will transfer you to a human agent.",
                        "handoff_required": True,
                        "handoff_reason": "Replacement request exceeds 7 days from delivery",
                        "intent": "completed",
                        "sub_intents": []
                    }
            except Exception as e:
                logger.error(f"Replacement date check failed: {e}")
                
        # Eligible! Generate alternatives and present them
        from app.services.recommendation import get_recommendations_service
        recs = get_recommendations_service(product_name, limit=2)
        
        if recs:
            bot_msg = f"I can help you replace your {product_name}. Would you like me to process a replacement for the same item, or would you prefer to try one of these alternatives instead?\n\n"
            alt_texts = []
            for r in recs:
                r_name = r.get("name", "")
                if "hydrating face wash" in r_name.lower():
                    note = "Good for dry skin"
                elif "aloe vera gel" in r_name.lower():
                    note = "Soothes sensitive skin"
                elif "daily cleanser" in r_name.lower():
                    note = "Gentle daily wash"
                elif "sunscreen" in r_name.lower():
                    note = "Soothes and protects skin"
                else:
                    note = f"Popular in {r.get('category', 'skincare')}"
                alt_texts.append(f"{r_name} ({note})*")
            bot_msg += "\n".join(alt_texts)
        else:
            bot_msg = f"I can help you replace your {product_name}. We did not find any matching alternative products. Would you like me to process a replacement for the same item?"
            
        return {
            "order_id": order_id,
            "bot_response": bot_msg,
            "replacement_offered": True,
            "recommended_products": recs
        }
    except Exception as e:
        logger.error(f"Replacement initialization error: {e}")
        return {"order_id": order_id, "bot_response": "Error processing replacement. Please try again later."}
