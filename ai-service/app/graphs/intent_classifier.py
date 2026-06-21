from app.models.state import AgentState
from app.nodes.classifier import classify_node
from app.nodes.processors import process_shipping_update, process_greeting, process_order_issue, process_default
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def start_router(state: AgentState) -> str:
    intent = state.get("intent")
    sub_intents = state.get("sub_intents", [])
    if intent == "order_issue" and "cancel_product" in sub_intents:
        return "order_issue"
    return "classify"

def router(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "shipping_address_update":
        return "shipping_update"
    elif intent == "greeting":
        return "greeting"
    elif intent == "order_issue":
        return "order_issue"
    else:
        return "default"

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("classify", classify_node)
    workflow.add_node("shipping_update", process_shipping_update)
    workflow.add_node("greeting", process_greeting)
    workflow.add_node("order_issue", process_order_issue)
    workflow.add_node("default", process_default)
    
    workflow.add_conditional_edges(
        START,
        start_router,
        {
            "order_issue": "order_issue",
            "classify": "classify"
        }
    )
    workflow.add_conditional_edges(
        "classify",
        router,
        {
            "shipping_update": "shipping_update",
            "greeting": "greeting",
            "order_issue": "order_issue",
            "default": "default"
        }
    )
    workflow.add_edge("shipping_update", END)
    workflow.add_edge("greeting", END)
    workflow.add_edge("order_issue", END)
    workflow.add_edge("default", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

intent_classifier_graph = create_graph()
