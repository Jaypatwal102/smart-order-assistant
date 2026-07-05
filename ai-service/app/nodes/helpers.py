import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.llm.ollama import get_llm
from app.models.state import ExtractionResult

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
