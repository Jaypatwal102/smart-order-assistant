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

    replacement_reason = state.get("replacement_reason")
    
    # 2. Extract and validate Order ID and replacement reason
    if not order_id:
        match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', message)
        if match:
            order_id = match.group(0)

    if not order_id or not replacement_reason:
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
            extracted_reason = res.get("replacement_reason")
            if extracted_reason:
                replacement_reason = extracted_reason
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
                
    if not order_id:
        return {"bot_response": "Please provide your exact order ID to proceed with your replacement.", "replacement_reason": replacement_reason}
        
    user_id = state.get("user_id")
    if not user_id:
        return {"order_id": order_id, "bot_response": "Session error: user ID is missing. Please log in again.", "replacement_reason": replacement_reason}
        
    try:
        url = f"http://localhost:8000/orders/{order_id}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 404:
            return {"order_id": None, "bot_response": f"Sorry, no order was found with ID '{order_id}'. Please try again.", "replacement_reason": replacement_reason}
        elif resp.status_code != 200:
            return {"order_id": None, "bot_response": "Error validating your order. Please try again later.", "replacement_reason": replacement_reason}
            
        order_data = resp.json()
        
        if str(order_data.get("user_id")).lower() != str(user_id).lower():
            return {"order_id": None, "bot_response": f"Sorry, order '{order_id}' is not associated with your account.", "intent": "completed", "sub_intents": [], "replacement_reason": replacement_reason}
            
        product_name = order_data.get("product_name")
        status = order_data.get("status", "")
        
        # Load replacement policy
        policy_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "replacement_policy.txt")
        with open(policy_path, "r", encoding="utf-8") as f:
            replacement_policy = f.read()

        current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        ordered_at_raw = order_data.get("ordered_at")
        ordered_at = ordered_at_raw.split("T")[0] if ordered_at_raw else "Unknown"
        
        delivered_at_raw = order_data.get("delivered_at")
        delivered_at = delivered_at_raw.split("T")[0] if delivered_at_raw else "Not delivered"
        
        from app.prompts.replacement_eval_prompt import REPLACEMENT_EVAL_PROMPT
        
        eval_prompt_str = REPLACEMENT_EVAL_PROMPT.format(
            replacement_policy=replacement_policy,
            product_name=product_name,
            status=status,
            ordered_at=ordered_at,
            delivered_at=delivered_at,
            current_date_str=current_date_str,
            reason=replacement_reason or message
        )
        from app.models.state import ReplacementEvaluationResult
        llm = get_llm()
        eval_parser = JsonOutputParser(pydantic_object=ReplacementEvaluationResult)
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
            elif status.lower() != "delivered":
                eval_res["eligible"] = False
                eval_res["reason"] = f"Guardrail: Invalid delivery status '{status}'."
            elif status.lower() in ["cancelled", "refunded"]:
                eval_res["eligible"] = False
                eval_res["reason"] = f"Guardrail: Order already {status}."
            elif order_data.get("delivered_at"):
                try:
                    del_str = order_data.get('delivered_at').replace('Z', '')
                    delivered_date = datetime.datetime.fromisoformat(del_str).replace(tzinfo=None)
                    if (datetime.datetime.now() - delivered_date).days > 7:
                        eval_res["eligible"] = False
                        eval_res["reason"] = "Guardrail: 7-day replacement window exceeded."
                except Exception as e:
                    logger.error(f"Guardrail date check failed: {e}")

        if not eval_res.get("eligible") or eval_res.get("confidence", 0) < 70:
            reason = eval_res.get("reason", "Policy evaluation failed or confidence too low.")
            confidence = eval_res.get("confidence", 0)
            eligible = eval_res.get("eligible", False)
            product_match = eval_res.get("product_match", False)
            delivery_valid = eval_res.get("delivery_valid", False)
            
            if len(reason) > 250:
                truncated_reason = reason[:247] + "..."
            else:
                truncated_reason = reason
                
            bot_msg = f"I need to transfer you to a human agent to review your replacement request.\n\n[Debug Info]\nReplacement Reason Evaluated: {replacement_reason or message}\nReason: {truncated_reason}\nEligible: {eligible}\nProduct Match: {product_match}\nDelivery Valid: {delivery_valid}\nConfidence: {confidence}%"
            
            return {
                "order_id": order_id,
                "bot_response": bot_msg,
                "handoff_required": True,
                "handoff_reason": f"Replacement policy check failed: {truncated_reason}",
                "intent": "completed",
                "sub_intents": [],
                "replacement_reason": replacement_reason
            }
                
        # Eligible! Generate alternatives and present them
        from app.services.recommendation import get_recommendations_service
        recs = get_recommendations_service(product_name, limit=2)
        
        if recs:
            bot_msg = f"I can help you replace your {product_name}. Would you like me to process a replacement for the same item, or would you prefer to try one of these alternatives instead?\n\n"
            alt_texts = []
            for r in recs:
                r_name = r.get("name", "")
                note = r.get("description")
                if not note:
                    note = f"Popular in {r.get('category', 'skincare')}"
                alt_texts.append(f"{r_name} ({note})*")
            bot_msg += "\n".join(alt_texts)
        else:
            bot_msg = f"I can help you replace your {product_name}. We did not find any matching alternative products. Would you like me to process a replacement for the same item?"
            
        return {
            "order_id": order_id,
            "bot_response": bot_msg,
            "replacement_offered": True,
            "recommended_products": recs,
            "replacement_reason": replacement_reason
        }
    except Exception as e:
        logger.error(f"Replacement initialization error: {e}")
        return {"order_id": order_id, "bot_response": "Error processing replacement. Please try again later."}
