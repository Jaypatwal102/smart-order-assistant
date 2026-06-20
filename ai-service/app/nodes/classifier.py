import logging
from app.llm.ollama import get_llm
from app.models.state import AgentState, ClassificationResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """You are an intent classification service for a customer support chatbot.
Analyze the user message and classify it into exactly one of these intents:
You need to multilingual support for languages English, French, Russian, Hindi.

- greeting (e.g. "hi", "hello", "good morning")
- shipping_address_update (e.g. "update my shipping address")
- order_issue (e.g. "received the wrong product", "recommend another product", "cancel my order")
- human_handoff (e.g. "connect me to an agent")
- unknown (if confidence is low or it does not match the above)

Supported sub-intents (only for order_issue):
- replace_product (if the user wants to replace or exchange a damaged/incorrect product)
- cancel_product (if the user wants to cancel a product, request a refund, or cancel an order)
- product_recommendation (if the user asks for suggestions or product recommendations)

Examples:
User: "hello"
{{"intent": "greeting", "sub_intents": [], "confidence": 99, "language": "English"}}

User: "my lotion arrived broken, I want to cancel it"
{{"intent": "order_issue", "sub_intents": ["cancel_product"], "confidence": 95, "language": "English"}}
"""

def classify_node(state: AgentState) -> dict:
    llm = get_llm()
    parser = JsonOutputParser(pydantic_object=ClassificationResult)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CLASSIFY_PROMPT + "\n\n{format_instructions}"),
        ("user", "{message}")
    ])
    
    chain = prompt | llm | parser
    try:
        res = chain.invoke({
            "message": state["message"],
            "format_instructions": parser.get_format_instructions()
        })
        return {
            "intent": res.get("intent", "unknown"),
            "sub_intents": res.get("sub_intents", []),
            "confidence": res.get("confidence", 0),
            "language": res.get("language", "English")
        }
    except Exception as e:
        logger.error(f"Classification node failed: {e}")
        return {"intent": "unknown", "sub_intents": [], "confidence": 0, "language": "English"}
