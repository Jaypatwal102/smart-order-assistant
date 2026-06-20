from langchain_ollama import ChatOllama

def get_llm():
    return ChatOllama(
        model="gemma3:4b",
        temperature=0.1,
        base_url="http://localhost:11434"
    )
