from langchain_ollama import ChatOllama, OllamaEmbeddings

def get_llm():
    return ChatOllama(
        model="gemma3:4b",
        temperature=0.1,
        base_url="http://localhost:11434"
    )

def get_embeddings():
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )
