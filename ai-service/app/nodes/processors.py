import re
import logging
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
    return {}

def process_greeting(state: AgentState) -> dict:
    return {}

def process_order_issue(state: AgentState) -> dict:
    return {}

def process_default(state: AgentState) -> dict:
    return {}
