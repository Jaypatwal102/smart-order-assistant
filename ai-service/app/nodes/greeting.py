from app.models.state import AgentState

def process_greeting(state: AgentState) -> dict:
    return {"bot_response": "Hello! How can I help you today?"}
