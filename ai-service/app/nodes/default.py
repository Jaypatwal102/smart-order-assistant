from app.models.state import AgentState

def process_default(state: AgentState) -> dict:
    return {"bot_response": "Sorry, i cant help with that."}
