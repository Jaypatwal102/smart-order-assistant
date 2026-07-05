from app.models.state import AgentState

def process_default(state: AgentState) -> dict:
    return {"bot_response": "I didn't quite catch that. Could you please rephrase?"}
