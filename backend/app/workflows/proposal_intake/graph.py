from langgraph.graph import END, START, StateGraph

from app.workflows.proposal_intake.nodes import (
    aggregate_extractions,
    fan_out_process_proposals,
    human_review,
    load_proposals,
    mark_intake_complete,
    process_proposal,
    validate_prerequisites,
)
from app.workflows.proposal_intake.state import ProposalIntakeState


def _route_prerequisites(state: ProposalIntakeState) -> str:
    return END if state.get("error") else "load_proposals"


def _route_review(state: ProposalIntakeState) -> str:
    if state.get("reprocess_ids"):
        return "load_proposals"
    return "mark_intake_complete"


def build_proposal_intake_graph() -> StateGraph:
    builder = StateGraph(ProposalIntakeState)

    builder.add_node("validate_prerequisites", validate_prerequisites)
    builder.add_node("load_proposals", load_proposals)
    builder.add_node("process_proposal", process_proposal)
    builder.add_node("aggregate_extractions", aggregate_extractions)
    builder.add_node("human_review", human_review)
    builder.add_node("mark_intake_complete", mark_intake_complete)

    builder.add_edge(START, "validate_prerequisites")
    builder.add_conditional_edges("validate_prerequisites", _route_prerequisites, {
        END: END,
        "load_proposals": "load_proposals",
    })
    # fan-out: one process_proposal per submitted proposal
    builder.add_conditional_edges("load_proposals", fan_out_process_proposals)
    # all parallel branches converge at aggregate_extractions
    builder.add_edge("process_proposal", "aggregate_extractions")
    builder.add_edge("aggregate_extractions", "human_review")
    builder.add_conditional_edges("human_review", _route_review, {
        "load_proposals": "load_proposals",
        "mark_intake_complete": "mark_intake_complete",
    })
    builder.add_edge("mark_intake_complete", END)

    return builder
