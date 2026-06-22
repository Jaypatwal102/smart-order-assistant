import os
import re
import logging
import requests
import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.llm.ollama import get_llm
from app.models.state import AgentState, ExtractionResult, RefundEvaluationResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract any customer entities from the user message.
Specifically look for:
- order_id: A 36-character UUID string (e.g., '12345678-1234-1234-1234-123456789012')
- new_address: A new shipping/delivery address description.
- refund_reason: The reason the user wants a refund (if any).

If any entity is not present, return null for it.
"""

class OfferResponseClassification(BaseModel):
    decision: str = Field(description="One of: 'accept_alternative', 'accept_same', 'check_recommendation', 'decline', 'unknown'")
    chosen_product: Optional[str] = Field(None, description="The name of the alternative product chosen, if decision is 'accept_alternative' or 'check_recommendation'")

def classify_response_to_offer(message: str, offer_type: str, recommended_products: Optional[List[Dict[str, Any]]]) -> dict:
    try:
        llm = get_llm()
        parser = JsonOutputParser(pydantic_object=OfferResponseClassification)
        
        products_str = ", ".join([p.get("name") for p in recommended_products]) if recommended_products else "None"
        
        prompt_text = f"""Analyze the user's message in response to an offer.
Offer Type: {offer_type}
Recommended alternative products: {products_str}

Classify the user's decision into one of these categories:
- 'accept_alternative': The user wants to exchange the item for one of the recommended alternative products.
- 'accept_same': The user wants to proceed with a replacement for the SAME product they originally ordered.
- 'check_recommendation': The user wants to check out, view, or look at the recommended alternative products or agrees to check them out.
- 'decline': The user declines the alternatives/retention offer (e.g., they still want the refund, or they say no/cancel).
- 'unknown': If it's not clear or they asked something else.

If they chose or mentioned a specific alternative product from the recommended list, identify it and return its exact name in 'chosen_product'.

Examples:
1. User: "yes, I'd like the Daily Cleanser" -> decision='accept_alternative', chosen_product='Daily Cleanser'
2. User: "replace with same product" -> decision='accept_same', chosen_product=null
3. User: "Sure, let me check the Hydrating Face Wash" -> decision='check_recommendation', chosen_product='Hydrating Face Wash'
4. User: "no thanks, just refund it" -> decision='decline', chosen_product=null
5. User: "no" -> decision='decline', chosen_product=null
6. User: "Refund" -> decision='decline', chosen_product=null
"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_text + "\n\n{format_instructions}"),
            ("user", "{message}")
        ])
        chain = prompt | llm | parser
        res = chain.invoke({
            "message": message,
            "format_instructions": parser.get_format_instructions()
        })
        return res
    except Exception as e:
        logger.error(f"Error classifying response to offer: {e}")
        return {"decision": "unknown", "chosen_product": None}

def process_shipping_update(state: AgentState) -> dict:
    return {"bot_response": "Shipping address update should be handled by Rasa."}

def process_greeting(state: AgentState) -> dict:
    return {"bot_response": "Hello! How can I help you today?"}

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
            alt1 = recs[0]["name"] if recs else "Retinol Serum"
            alt2 = recs[1]["name"] if len(recs) > 1 else "Ceramide Moisturizer"
            bot_msg += f" If you are looking for an alternative, you might like our {alt1} or {alt2}. Would you like to check either of these out?"
            
            return {
                "order_id": order_id,
                "bot_response": bot_msg,
                "cancel_offered": True,
                "recommended_products": recs or [
                    {"name": "Retinol Serum", "category": "Serum"},
                    {"name": "Ceramide Moisturizer", "category": "Moisturizer"}
                ]
            }
        else:
            error_detail = cancel_resp.json().get("detail", "Unknown error")
            return {"order_id": None, "bot_response": f"Failed to cancel order: {error_detail}", "intent": "completed", "sub_intents": []}
            
    except Exception as e:
        logger.error(f"Order issue API error: {e}")
        return {"order_id": order_id, "bot_response": "Error contacting the server. Please try again later."}

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
            # "in replacement say thankyou and reoder the same product"
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
            bot_msg = "I didn't catch that. Would you like me to process a replacement for the same item, or would you prefer one of the alternatives?"
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
        
        bot_msg = f"I can help you replace your {product_name}. Would you like me to process a replacement for the same item, or would you prefer to try one of these alternatives instead?\n\n"
        
        # Helper to format alternatives with notes
        if recs:
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
            bot_msg += "Hydrating Face Wash (Good for dry skin)*\nAloe Vera Gel (Soothes sensitive skin)*"
            
        return {
            "order_id": order_id,
            "bot_response": bot_msg,
            "replacement_offered": True,
            "recommended_products": recs or [
                {"name": "Hydrating Face Wash", "category": "Cleanser"},
                {"name": "Aloe Vera Gel", "category": "Gel"}
            ]
        }
    except Exception as e:
        logger.error(f"Replacement initialization error: {e}")
        return {"order_id": order_id, "bot_response": "Error processing replacement. Please try again later."}

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

        
        EVAL_PROMPT = f"""You are an AI assistant evaluating a refund request.
Here is the refund policy:
{refund_policy}

Order details:
- Product Name: {order_data.get('product_name', 'Unknown')}
- Status: {order_data.get('status', 'unknown')}
- Ordered At: {ordered_at}
- Delivered At: {delivered_at}
- Current Date: {current_date_str}

The user's reason for a refund is: "{refund_reason or message}"

CRITICAL INSTRUCTIONS

You are a strict refund compliance officer.

Your default decision is NOT ELIGIBLE.

You may set eligible=true ONLY if every required condition is explicitly satisfied by the order data and refund policy.

Never assume facts that are not provided.

If information is missing, unclear, contradictory, or cannot be verified from the order data, set eligible=false. Note: The user's claim of "arrived damaged", "defective", or "wrong product" is the input reason. You do not need database proof of the damage or mistake itself. If status is "delivered" and the request is within 7 days, and they claim damage or wrong product, consider the claim valid and satisfy the eligibility condition.

Required checks:

1. Order Verification

* Order must exist.
* Order must belong to the customer.
* Order status must support the claim.

2. Delivery Verification

* For wrong product, damaged product, or defective product claims:

  * status MUST be "delivered"
  * delivered_at MUST exist
* Otherwise eligible=false.

3. Refund Window Verification

* Request must be within 7 days of delivered_at.
* If unable to verify delivery date, eligible=false.

4. Reason Verification

* The user's reason must match an approved refund scenario from the policy.
* Standard user descriptions like "arrived damaged", "broken", "defective", "wrong product", or "did not receive it" are explicitly approved and are NOT vague. If the user states one of these reasons, consider it a valid matching reason.

5. Product Consistency Verification

* The claim must be consistent with the actual product in the order.
* If the claim is impossible, absurd, or unrelated to the product, eligible=false.

6. Strict Rejection Rules
   Automatically reject if:

* Customer changed their mind.
* Customer no longer wants the product.
* Customer dislikes the product.
* Request is outside the refund window.
* Product was delivered correctly.
* Information is missing.
* Policy does not explicitly allow the refund.

Confidence Rules:

* 95-100 = Policy clearly allows refund.
* 70-94 = Some uncertainty exists.
* Below 70 = Refund must not be auto-approved.

IMPORTANT:
If there is any uncertainty whatsoever, set eligible=false.
Only approve when the policy clearly and explicitly permits the refund.

Output a JSON with:
- product_match: boolean (true if the user's claim logically matches the actual Product Name in the order details, false if absurd/fake)
- delivery_valid: boolean (true if order has a 'delivered' status with a valid date, false otherwise)
- eligible: boolean (true ONLY IF policy allows it AND product_match is true AND delivery_valid is true AND within 7 days, false otherwise)
- confidence: integer from 0 to 100 representing your confidence in this decision
- reason: string explaining your decision based on the policy. Keep this EXTREMELY concise (under 200 characters).

Only output the JSON.
"""
        eval_parser = JsonOutputParser(pydantic_object=RefundEvaluationResult)
        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", EVAL_PROMPT + "\n\n{format_instructions}")
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
            
            alt1 = recs[0]["name"] if recs else "Daily Cleanser"
            alt2 = recs[1]["name"] if len(recs) > 1 else "Sunscreen SPF 50"
            
            bot_msg = f"I can see you're eligible for a refund on the {order_data.get('product_name')}. Before I process it, would you be interested in exchanging it for our {alt1} or {alt2} instead? If you still prefer a refund, just say 'Refund' and I will process it immediately."
            
            return {
                "order_id": order_id,
                "bot_response": bot_msg,
                "refund_offered": True,
                "recommended_products": recs or [
                    {"name": "Daily Cleanser", "category": "Cleanser"},
                    {"name": "Sunscreen SPF 50", "category": "Sunscreen"}
                ],
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

def process_default(state: AgentState) -> dict:
    return {"bot_response": "I didn't quite catch that. Could you please rephrase?"}

def process_human_handoff(state: AgentState) -> dict:
    return {
        "bot_response": "I am transferring you to a human agent now.",
        "handoff_required": True,
        "handoff_reason": "User requested human handoff."
    }
