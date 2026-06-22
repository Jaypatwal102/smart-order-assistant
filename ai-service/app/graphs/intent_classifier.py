from app.models.state import AgentState
from app.nodes.classifier import classify_node
from app.nodes.processors import process_shipping_update, process_greeting, process_order_issue, process_refund, process_default, process_human_handoff
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def start_router(state: AgentState) -> str:
    intent = state.get("intent")
    sub_intents = state.get("sub_intents", [])
    if intent == "order_issue" and "cancel_product" in sub_intents:
        return "order_issue"
    if intent == "order_issue" and "refund" in sub_intents:
        return "refund"
    return "classify"

def router(state: AgentState) -> str:
    intent = state.get("intent")
    sub_intents = state.get("sub_intents", [])
    if intent == "shipping_address_update":
        return "shipping_update"
    elif intent == "greeting":
        return "greeting"
    elif intent == "human_handoff":
        return "human_handoff"
    elif intent == "order_issue":
        if "refund" in sub_intents:
            return "refund"
        return "order_issue"
    else:
        return "default"

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("classify", classify_node)
    workflow.add_node("shipping_update", process_shipping_update)
    workflow.add_node("greeting", process_greeting)
    workflow.add_node("order_issue", process_order_issue)
    workflow.add_node("refund", process_refund)
    workflow.add_node("human_handoff", process_human_handoff)
    workflow.add_node("default", process_default)
    
    workflow.add_conditional_edges(
        START,
        start_router,
        {
            "order_issue": "order_issue",
            "refund": "refund",
            "classify": "classify"
        }
    )
    workflow.add_conditional_edges(
        "classify",
        router,
        {
            "shipping_update": "shipping_update",
            "greeting": "greeting",
            "human_handoff": "human_handoff",
            "order_issue": "order_issue",
            "refund": "refund",
            "default": "default"
        }
    )
    workflow.add_edge("shipping_update", END)
    workflow.add_edge("greeting", END)
    workflow.add_edge("order_issue", END)
    workflow.add_edge("refund", END)
    workflow.add_edge("human_handoff", END)
    workflow.add_edge("default", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

intent_classifier_graph = create_graph()
