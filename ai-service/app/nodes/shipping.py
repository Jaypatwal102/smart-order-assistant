from app.models.state import AgentState

def process_shipping_update(state: AgentState) -> dict:
    return {"bot_response": "Shipping address update should be handled by Rasa."}
