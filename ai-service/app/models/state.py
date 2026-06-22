from typing import List, Optional, TypedDict
from pydantic import BaseModel, Field

class ClassificationResult(BaseModel):
    intent: str = Field(
        description="The primary intent. Must be one of: greeting, shipping_address_update, order_issue, human_handoff, unknown."
    )
    sub_intents: List[str] = Field(
        default=[],
        description="Sub-intents. Only populated for order_issue: replace_product, cancel_product, product_recommendation."
    )
    confidence: int = Field(description="Confidence score between 0 and 100.")
    language: str = Field(default="English", description="Detected language (e.g. English, French, Russian, Hindi).")

class ExtractionResult(BaseModel):
    order_id: Optional[str] = Field(None, description="A 36-character UUID/order ID if found in the user message.")
    new_address: Optional[str] = Field(None, description="A new shipping/delivery address if found in the user message.")
    refund_reason: Optional[str] = Field(None, description="The full, detailed reason the user wants a refund, retaining all specific details.")

class RefundEvaluationResult(BaseModel):
    product_match: bool = Field(description="true if user's claim matches actual product in order, false if absurd/fake")
    delivery_valid: bool = Field(description="true if status is 'delivered' with a valid date, false otherwise")
    eligible: bool = Field(description="true only if policy allows refund, product matches, delivery is valid, and within 7 days")
    confidence: int = Field(description="confidence score between 0 and 100")
    reason: str = Field(description="very concise reason explaining decision (under 200 characters)")

class AgentState(TypedDict):
    message: str
    conversation_id: str
    intent: str
    sub_intents: List[str]
    confidence: int
    language: str
    # Persistent entities managed across turns
    order_id: Optional[str]
    new_address: Optional[str]
    user_id: Optional[str]
    refund_offered: Optional[bool]
    cancel_offered: Optional[bool]
    replacement_offered: Optional[bool]
    recommended_products: Optional[List[dict]]
    refund_reason: Optional[str]
    bot_response: Optional[str]
    handoff_required: Optional[bool]
    handoff_reason: Optional[str]
