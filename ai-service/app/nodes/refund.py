import re
import os
import datetime
import logging
import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.llm.ollama import get_llm
from app.models.state import AgentState, ExtractionResult, RefundEvaluationResult
from app.nodes.helpers import classify_response_to_offer, EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

def process_refund(state: AgentState) -> dict:
    order_id = state.get("order_id")
    message = state.get("message", "")
    refund_reason = state.get("refund_reason")
    
    # 1. Handle refund retention follow-up
    if state.get("refund_offered"):
        recommended = state.get("recommended_products") or []
        res = classify_response_to_offer(message, "refund_retention", recommended)
        decision = res.get("decision", "unknown")
        chosen_product = res.get("chosen_product")
        
        if decision == "accept_alternative":
            prod = chosen_product or (recommended[0]["name"] if recommended else "alternative product")
            try:
                replace_url = f"http://localhost:8000/orders/{order_id}/replace"
                replace_resp = requests.post(replace_url, json={"replacement_product_name": prod}, timeout=5)
                if replace_resp.status_code == 200:
                    bot_msg = f"Thank you! I have processed a replacement order for **{prod}** instead of a refund. Your new order is being processed."
                    return {
                        "bot_response": bot_msg,
                        "refund_offered": False,
                        "recommended_products": None,
                        "intent": "completed",
                        "sub_intents": []
                    }
            except Exception as e:
                logger.error(f"Failed to process replacement in refund follow-up: {e}")
            
            bot_msg = f"There was an error processing the exchange for **{prod}**. I will transfer you to a human agent now."
            return {
                "bot_response": bot_msg,
                "handoff_required": True,
                "handoff_reason": "Refund replacement API failed",
                "refund_offered": False,
                "recommended_products": None,
                "intent": "completed",
                "sub_intents": []
            }
            
        elif decision == "check_recommendation":
            bot_msg = "Great! You can order it from here: http://example.com/order-alternative"
            return {
                "bot_response": bot_msg,
                "refund_offered": False,
                "recommended_products": None,
                "intent": "completed",
                "sub_intents": []
            }
            
        elif decision == "decline":
            # "if not agree then in refund just do human handoff"
            bot_msg = "I am transferring you to a human agent now to process your refund."
            return {
                "bot_response": bot_msg,
                "handoff_required": True,
                "handoff_reason": "Customer declined refund retention offer",
                "refund_offered": False,
                "recommended_products": None,
                "intent": "completed",
                "sub_intents": []
            }
            
        else:
            bot_msg = "I didn't catch that. If you still prefer a refund, just say 'Refund' and I will transfer you to an agent. Otherwise, let me know if you would like to exchange it."
            return {
                "bot_response": bot_msg
            }
            
    if not order_id:
        match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', message)
        if match:
            order_id = match.group(0)

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
        if not order_id:
            order_id = res.get("order_id")
            
        extracted_reason = res.get("refund_reason")
        if extracted_reason and str(extracted_reason).strip():
            clean_reason = str(extracted_reason).strip()
            if clean_reason.lower() not in ["null", "none", "n/a", "no", "false"]:
                if not refund_reason or len(clean_reason) > len(str(refund_reason)):
                    refund_reason = clean_reason
    except Exception as e:
        logger.error(f"Extraction failed: {e}")

    if not order_id:
        return {
            "bot_response": "Please provide your exact order ID so I can look up your order for a refund.",
            "refund_reason": refund_reason
        }
    
    user_id = state.get("user_id")
    if not user_id:
        return {
            "order_id": order_id, 
            "bot_response": "Session error: user ID is missing. Please log in again.",
            "refund_reason": refund_reason
        }
        
    try:
        url = f"http://localhost:8000/orders/{order_id}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 404:
            return {
                "order_id": None, 
                "bot_response": f"Sorry, no order was found with ID '{order_id}'. Please try again.",
                "refund_reason": refund_reason
            }
        elif resp.status_code != 200:
            return {
                "order_id": None, 
                "bot_response": "Error validating your order. Please try again later.",
                "refund_reason": refund_reason
            }
            
        order_data = resp.json()
        
        if str(order_data.get("user_id")).lower() != str(user_id).lower():
            return {
                "order_id": None, 
                "bot_response": f"Sorry, order '{order_id}' is not associated with your account.", 
                "intent": "completed", 
                "sub_intents": [],
                "refund_reason": refund_reason
            }
            
        # Read the refund policy
        policy_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "refund_policy.txt")
        with open(policy_path, "r") as f:
            refund_policy = f.read()

        current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        ordered_at_raw = order_data.get("ordered_at")
        ordered_at = ordered_at_raw.split("T")[0] if ordered_at_raw else "Unknown"
        
        delivered_at_raw = order_data.get("delivered_at")
        delivered_at = delivered_at_raw.split("T")[0] if delivered_at_raw else "Not delivered"

        
        from app.prompts.refund_eval_prompt import REFUND_EVAL_PROMPT
        
        eval_prompt_str = REFUND_EVAL_PROMPT.format(
            refund_policy=refund_policy,
            product_name=order_data.get('product_name', 'Unknown'),
            status=order_data.get('status', 'unknown'),
            ordered_at=ordered_at,
            delivered_at=delivered_at,
            current_date_str=current_date_str,
            reason=refund_reason or message
        )
        eval_parser = JsonOutputParser(pydantic_object=RefundEvaluationResult)
        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", eval_prompt_str + "\n\n{format_instructions}")
        ])
        eval_chain = eval_prompt | llm | eval_parser
        eval_res = eval_chain.invoke({
            "format_instructions": eval_parser.get_format_instructions()
        })
        
        # HARD PROGRAMMATIC GUARDRAILS
        if eval_res.get("eligible"):
            if not eval_res.get("product_match"):
                eval_res["eligible"] = False
                eval_res["reason"] = "Guardrail: Product mismatch detected."
            elif not eval_res.get("delivery_valid") and order_data.get('status') != 'cancelled':
                eval_res["eligible"] = False
                eval_res["reason"] = f"Guardrail: Invalid delivery status '{order_data.get('status')}'."
            elif order_data.get('status') == 'delivered' and order_data.get('delivered_at'):
                try:
                    del_str = order_data.get('delivered_at').replace('Z', '')
                    delivered_date = datetime.datetime.fromisoformat(del_str).replace(tzinfo=None)
                    if (datetime.datetime.now() - delivered_date).days > 7:
                        eval_res["eligible"] = False
                        eval_res["reason"] = "Guardrail: 7-day refund window exceeded."
                except Exception as e:
                    logger.error(f"Guardrail date check failed: {e}")
        
        if eval_res.get("eligible") and eval_res.get("confidence", 0) >= 70:
            # 2. Present retention offer first
            from app.services.recommendation import get_recommendations_service
            recs = get_recommendations_service(order_data.get('product_name'), limit=2)
            
            if not recs:
                bot_msg = f"I can see you're eligible for a refund on the {order_data.get('product_name')}. Sorry, we didn't find any matching products for an exchange. I am transferring you to a human agent now to process your refund."
                return {
                    "order_id": order_id,
                    "bot_response": bot_msg,
                    "handoff_required": True,
                    "handoff_reason": "No matching exchange products found for eligible refund",
                    "refund_offered": False,
                    "recommended_products": [],
                    "refund_reason": refund_reason
                }
            
            if len(recs) == 1:
                alt1 = recs[0]["name"]
                bot_msg = f"I can see you're eligible for a refund on the {order_data.get('product_name')}. Before I process it, would you be interested in exchanging it for our {alt1} instead? If you still prefer a refund, just say 'Refund' and I will process it immediately."
            else:
                alt1 = recs[0]["name"]
                alt2 = recs[1]["name"]
                bot_msg = f"I can see you're eligible for a refund on the {order_data.get('product_name')}. Before I process it, would you be interested in exchanging it for our {alt1} or {alt2} instead? If you still prefer a refund, just say 'Refund' and I will process it immediately."
            
            return {
                "order_id": order_id,
                "bot_response": bot_msg,
                "refund_offered": True,
                "recommended_products": recs,
                "refund_reason": refund_reason
            }
        else:
            reason = eval_res.get("reason", "Policy evaluation failed or confidence too low.")
            confidence = eval_res.get("confidence", 0)
            eligible = eval_res.get("eligible", False)
            product_match = eval_res.get("product_match", False)
            delivery_valid = eval_res.get("delivery_valid", False)
            
            if len(reason) > 250:
                truncated_reason = reason[:247] + "..."
            else:
                truncated_reason = reason
                
            bot_msg = f"I need to transfer you to a human agent to review your refund request.\n\n[Debug Info]\nRefund Reason Evaluated: {refund_reason or message}\nReason: {reason}\nEligible: {eligible}\nProduct Match: {product_match}\nDelivery Valid: {delivery_valid}\nConfidence: {confidence}%"
            
            return {
                "order_id": order_id, 
                "bot_response": bot_msg,
                "handoff_required": True,
                "handoff_reason": truncated_reason,
                "refund_reason": refund_reason
            }
            
    except Exception as e:
        logger.error(f"Refund evaluation error: {e}")
        return {
            "order_id": order_id, 
            "bot_response": "Error evaluating your refund. I will transfer you to a human agent.", 
            "handoff_required": True, 
            "handoff_reason": "Internal error during refund evaluation",
            "refund_reason": refund_reason
        }
