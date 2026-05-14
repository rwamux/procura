from langgraph.graph import END, START, StateGraph

from app.workflows.evaluation.nodes import (
    apply_override,
    fan_out_scoring,
    finalize_selection,
    generate_recommendation_rationale,
    human_review,
    load_extracted_proposals,
    rank_proposals,
    score_proposal,
    validate_prerequisites,
)
from app.workflows.evaluation.state import EvaluationState


def _route_prerequisites(state: EvaluationState) -> str:
    return END if state.get("error") else "load_extracted_proposals"


def _route_approval(state: EvaluationState) -> str:
    action = state.get("approval_action", "")
    if action == "MANUAL_OVERRIDE":
        return "apply_override"
    return "finalize_selection"


def build_evaluation_graph() -> StateGraph:
    builder = StateGraph(EvaluationState)

    builder.add_node("validate_prerequisites", validate_prerequisites)
    builder.add_node("load_extracted_proposals", load_extracted_proposals)
    builder.add_node("score_proposal", score_proposal)
    builder.add_node("rank_proposals", rank_proposals)
    builder.add_node("generate_recommendation_rationale", generate_recommendation_rationale)
    builder.add_node("human_review", human_review)
    builder.add_node("apply_override", apply_override)
    builder.add_node("finalize_selection", finalize_selection)

    builder.add_edge(START, "validate_prerequisites")
    builder.add_conditional_edges("validate_prerequisites", _route_prerequisites, {
        END: END,
        "load_extracted_proposals": "load_extracted_proposals",
    })
    # Fan-out: one score_proposal per extracted proposal
    builder.add_conditional_edges("load_extracted_proposals", fan_out_scoring)
    # All scoring branches converge at rank_proposals
    builder.add_edge("score_proposal", "rank_proposals")
    builder.add_edge("rank_proposals", "generate_recommendation_rationale")
    builder.add_edge("generate_recommendation_rationale", "human_review")
    builder.add_conditional_edges("human_review", _route_approval, {
        "apply_override": "apply_override",
        "finalize_selection": "finalize_selection",
    })
    builder.add_edge("apply_override", "finalize_selection")
    builder.add_edge("finalize_selection", END)

    return builder
