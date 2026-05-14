from langgraph.graph import END, START, StateGraph

from app.workflows.contract.nodes import (
    assemble_contract,
    escalate,
    fan_out_sections,
    finalize_contract,
    generate_section,
    human_review,
    load_contract_context,
    mark_rejected,
    store_revision,
    validate_complete_contract,
    validate_prerequisites,
)
from app.workflows.contract.state import CONTRACT_SECTIONS, ContractState


def _route_prerequisites(state: ContractState) -> str:
    return END if state.get("error") else "load_contract_context"


def _route_validation(state: ContractState) -> str:
    if not state.get("validation_error"):
        return "human_review"
    if state.get("validation_attempts", 0) >= 3:
        return "escalate"
    return "load_contract_context"  # retry by reloading + re-fanning


def _route_approval(state: ContractState) -> str:
    action = state.get("approval_action", "")
    if action == "APPROVED":
        return "finalize_contract"
    if action == "REVISION_REQUESTED":
        return "store_revision"
    return "mark_rejected"


def build_contract_graph() -> StateGraph:
    builder = StateGraph(ContractState)

    builder.add_node("validate_prerequisites", validate_prerequisites)
    builder.add_node("load_contract_context", load_contract_context)
    builder.add_node("generate_section", generate_section)
    builder.add_node("assemble_contract", assemble_contract)
    builder.add_node("validate_complete_contract", validate_complete_contract)
    builder.add_node("escalate", escalate)
    builder.add_node("human_review", human_review)
    builder.add_node("finalize_contract", finalize_contract)
    builder.add_node("store_revision", store_revision)
    builder.add_node("mark_rejected", mark_rejected)

    builder.add_edge(START, "validate_prerequisites")
    builder.add_conditional_edges("validate_prerequisites", _route_prerequisites, {
        END: END,
        "load_contract_context": "load_contract_context",
    })
    # Fan-out: one generate_section per contract section (parallel)
    builder.add_conditional_edges("load_contract_context", fan_out_sections)
    # All section branches converge at assemble_contract
    builder.add_edge("generate_section", "assemble_contract")
    builder.add_edge("assemble_contract", "validate_complete_contract")
    builder.add_conditional_edges("validate_complete_contract", _route_validation, {
        "human_review": "human_review",
        "escalate": "escalate",
        "load_contract_context": "load_contract_context",
    })
    builder.add_edge("escalate", END)
    builder.add_conditional_edges("human_review", _route_approval, {
        "finalize_contract": "finalize_contract",
        "store_revision": "store_revision",
        "mark_rejected": "mark_rejected",
    })
    builder.add_conditional_edges("store_revision", fan_out_sections)
    builder.add_edge("finalize_contract", END)
    builder.add_edge("mark_rejected", END)

    return builder
