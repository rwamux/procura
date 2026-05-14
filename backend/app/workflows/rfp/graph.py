from langgraph.graph import END, START, StateGraph

from app.workflows.rfp.nodes import (
    escalate_to_human,
    generate_rfp,
    human_review,
    load_requirements,
    mark_rejected,
    persist_approved_rfp,
    store_revision,
    validate_prerequisites,
    validate_rfp_structure,
)
from app.workflows.rfp.state import RFPState

MAX_VALIDATION_ATTEMPTS = 3


def _route_prerequisites(state: RFPState) -> str:
    return END if state.get("error") else "load_requirements"


def _route_validation(state: RFPState) -> str:
    if not state.get("validation_error"):
        return "human_review"
    if state.get("validation_attempts", 0) >= MAX_VALIDATION_ATTEMPTS:
        return "escalate_to_human"
    return "generate_rfp"


def _route_approval(state: RFPState) -> str:
    action = state.get("approval_action", "")
    if action == "APPROVED":
        return "persist_approved_rfp"
    if action == "REVISION_REQUESTED":
        return "store_revision"
    return "mark_rejected"


def build_rfp_graph() -> StateGraph:
    builder = StateGraph(RFPState)

    builder.add_node("validate_prerequisites", validate_prerequisites)
    builder.add_node("load_requirements", load_requirements)
    builder.add_node("generate_rfp", generate_rfp)
    builder.add_node("validate_rfp_structure", validate_rfp_structure)
    builder.add_node("escalate_to_human", escalate_to_human)
    builder.add_node("human_review", human_review)
    builder.add_node("persist_approved_rfp", persist_approved_rfp)
    builder.add_node("store_revision", store_revision)
    builder.add_node("mark_rejected", mark_rejected)

    builder.add_edge(START, "validate_prerequisites")
    builder.add_conditional_edges("validate_prerequisites", _route_prerequisites, {
        END: END,
        "load_requirements": "load_requirements",
    })
    builder.add_edge("load_requirements", "generate_rfp")
    builder.add_edge("generate_rfp", "validate_rfp_structure")
    builder.add_conditional_edges("validate_rfp_structure", _route_validation, {
        "human_review": "human_review",
        "escalate_to_human": "escalate_to_human",
        "generate_rfp": "generate_rfp",
    })
    builder.add_edge("escalate_to_human", END)
    builder.add_conditional_edges("human_review", _route_approval, {
        "persist_approved_rfp": "persist_approved_rfp",
        "store_revision": "store_revision",
        "mark_rejected": "mark_rejected",
    })
    builder.add_edge("store_revision", "generate_rfp")
    builder.add_edge("persist_approved_rfp", END)
    builder.add_edge("mark_rejected", END)

    return builder
