import os
import re
import logging
import requests
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

def process_refund(state: AgentState) -> dict:
    order_id = state.get("order_id")
    message = state.get("message", "")
    refund_reason = state.get("refund_reason")
    
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
        # Update refund reason if we found a substantive new reason
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

        import datetime
        current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        ordered_at = order_data.get("ordered_at", "Unknown")
        delivered_at = order_data.get("delivered_at", "Not delivered")
        
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

If information is missing, unclear, contradictory, or cannot be verified from the order data, set eligible=false.

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
* If the reason is vague, missing, or unsupported, eligible=false.

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
        
        # HARD PROGRAMMATIC GUARDRAILS (Overrides LLM if it hallucinates eligibility)
        if eval_res.get("eligible"):
            if not eval_res.get("product_match"):
                eval_res["eligible"] = False
                eval_res["reason"] = "Guardrail: Product mismatch detected."
            elif not eval_res.get("delivery_valid") and order_data.get('status') != 'cancelled':
                eval_res["eligible"] = False
                eval_res["reason"] = f"Guardrail: Invalid delivery status '{order_data.get('status')}'."
            elif order_data.get('status') == 'delivered' and order_data.get('delivered_at'):
                try:
                    # Strip any Z or timezone info to make it naive for safe subtraction with datetime.now()
                    del_str = order_data.get('delivered_at').replace('Z', '')
                    delivered_date = datetime.datetime.fromisoformat(del_str).replace(tzinfo=None)
                    if (datetime.datetime.now() - delivered_date).days > 7:
                        eval_res["eligible"] = False
                        eval_res["reason"] = "Guardrail: 7-day refund window exceeded."
                except Exception as e:
                    logger.error(f"Guardrail date check failed: {e}")
        
        if eval_res.get("eligible") and eval_res.get("confidence", 0) >= 90:
            refund_url = f"http://localhost:8000/orders/{order_id}/refund"
            refund_resp = requests.post(refund_url, timeout=5)
            if refund_resp.status_code == 200:
                return {
                    "order_id": order_id, 
                    "bot_response": f"Good news! Your refund for order '{order_id}' has been automatically processed.", 
                    "intent": "completed", 
                    "sub_intents": [],
                    "refund_reason": refund_reason
                }
            else:
                return {
                    "order_id": None, 
                    "bot_response": "There was an error processing your refund. I will transfer you to a human agent.", 
                    "handoff_required": True, 
                    "handoff_reason": "Refund API failed",
                    "refund_reason": refund_reason
                }
        else:
            reason = eval_res.get("reason", "Policy evaluation failed or confidence too low.")
            confidence = eval_res.get("confidence", 0)
            eligible = eval_res.get("eligible", False)
            product_match = eval_res.get("product_match", False)
            delivery_valid = eval_res.get("delivery_valid", False)
            
            # Ensure it fits within the 255 character limit in the database
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
