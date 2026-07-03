import os
import json
import logging
from app.llm.ollama import get_llm
from app.models.state import AgentState, ClassificationResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)

# Load prompts and intents from configuration files
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
INTENT_PATH = os.path.join(PROMPTS_DIR, "intent.json")
PROMPT_PATH = os.path.join(PROMPTS_DIR, "prompt.txt")

try:
    with open(INTENT_PATH, "r", encoding="utf-8") as f:
        INTENT_DATA = json.load(f)
    
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        PROMPT_TEMPLATE = f.read()

    # Dynamically build the lists of intents and sub_intents
    intents_list = [info["description"] for info in INTENT_DATA["intents"].values()]
    sub_intents_list = [info["description"] for info in INTENT_DATA["sub_intents"].values()]

    intents_block = "\n".join(f"- {desc}" for desc in intents_list)
    sub_intents_block = "\n".join(f"- {desc}" for desc in sub_intents_list)

    CLASSIFY_PROMPT = PROMPT_TEMPLATE.replace("{intents}", intents_block).replace("{sub_intents}", sub_intents_block)
except Exception as e:
    logger.error(f"Failed to load prompt/intent configuration: {e}")
    CLASSIFY_PROMPT = ""
    INTENT_DATA = {"intents": {}, "sub_intents": {}}

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
        
        intent = res.get("intent", "unknown")
        sub_intents = list(res.get("sub_intents") or [])
        msg_lower = state["message"].lower()
        
        # Rule-based programmatic fallbacks to ensure robust sub_intent classification
        for sub_intent_name, sub_intent_info in INTENT_DATA.get("sub_intents", {}).items():
            fallback_keywords = sub_intent_info.get("fallback_keywords", [])
            parent_intent = sub_intent_info.get("parent_intent")
            
            # Check if any fallback keyword is in the user message
            if any(kw in msg_lower for kw in fallback_keywords):
                if parent_intent:
                    intent = parent_intent
                if sub_intent_name not in sub_intents:
                    sub_intents.append(sub_intent_name)
                
        return {
            "intent": intent,
            "sub_intents": sub_intents,
            "confidence": res.get("confidence", 0),
            "language": res.get("language", "English")
        }
    except Exception as e:
        logger.error(f"Classification node failed: {e}")
        return {"intent": "unknown", "sub_intents": [], "confidence": 0, "language": "English"}

