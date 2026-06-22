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
