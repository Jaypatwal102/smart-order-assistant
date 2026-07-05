from app.models.state import AgentState

def process_human_handoff(state: AgentState) -> dict:
    return {
        "bot_response": "I am transferring you to a human agent now.",
        "handoff_required": True,
        "handoff_reason": "User requested human handoff."
    }
