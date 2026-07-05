import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.llm.ollama import get_llm
from app.models.state import ExtractionResult

logger = logging.getLogger(__name__)

from app.prompts.extraction_prompt import EXTRACTION_PROMPT
from app.prompts.offer_classification_prompt import OFFER_CLASSIFICATION_PROMPT

class OfferResponseClassification(BaseModel):
    decision: str = Field(description="One of: 'accept_alternative', 'accept_same', 'check_recommendation', 'decline', 'unknown'")
    chosen_product: Optional[str] = Field(None, description="The name of the alternative product chosen, if decision is 'accept_alternative' or 'check_recommendation'")

def classify_response_to_offer(message: str, offer_type: str, recommended_products: Optional[List[Dict[str, Any]]]) -> dict:
    try:
        llm = get_llm()
        parser = JsonOutputParser(pydantic_object=OfferResponseClassification)
        
        products_str = ", ".join([p.get("name") for p in recommended_products]) if recommended_products else "None"
        
        prompt_text = OFFER_CLASSIFICATION_PROMPT.format(
            offer_type=offer_type,
            products_str=products_str
        )
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
