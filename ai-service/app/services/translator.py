import re
import logging
from app.llm.ollama import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

async def translate_text_service(text: str, target_language: str, source_language: str = None) -> str:
    if target_language.lower() in ["en", "english"] and (source_language is None or source_language.lower() in ["en", "english"]):
        return text
        
    if source_language and target_language.lower() == source_language.lower():
        return text
        
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Translate the following text to {target_language}. Do not output any thinking tags. Do not explain anything. Just output the precise translated text and nothing else."),
        ("user", "Text: {text}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        translated = await chain.ainvoke({"text": text, "target_language": target_language})
        translated = translated.strip()
        
        # Clean up potential markdown formatting and tags (e.g. <think> tags)
        translated = re.sub(r'<think>.*?</think>', '', translated, flags=re.DOTALL).strip()
        
        if not translated:
            return text
        return translated
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text
