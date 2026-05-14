"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="PROCUREMENT_OFFICER"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "procurements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("business_objective", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("budget_min", sa.Numeric(), nullable=True),
        sa.Column("budget_max", sa.Numeric(), nullable=True),
        sa.Column("budget_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("timeline", sa.String(), nullable=False),
        sa.Column("evaluation_criteria", JSONB(), nullable=False, server_default="[]"),
        sa.Column("compliance_requirements", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False, server_default="RFP"),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("selected_proposal_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rfps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("prompt_metadata", JSONB(), nullable=True),
        sa.Column("generation_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rfp_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rfp_id", UUID(as_uuid=True), sa.ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("revision_request", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "supplier_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_name", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_data", JSONB(), nullable=True),
        sa.Column("extraction_model", sa.String(), nullable=True),
        sa.Column("extraction_status", sa.String(), nullable=False, server_default="SUBMITTED"),
        sa.Column("status", sa.String(), nullable=False, server_default="SUBMITTED"),
        sa.Column("upload_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("extraction_timestamp", sa.DateTime(timezone=True), nullable=True),
    )

    # Now add the circular FK: procurements.selected_proposal_id → supplier_proposals
    op.create_foreign_key(
        "fk_procurement_selected_proposal",
        "procurements",
        "supplier_proposals",
        ["selected_proposal_id"],
        ["id"],
        use_alter=True,
    )

    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("evaluation_weights", JSONB(), nullable=False),
        sa.Column("recommendation_proposal_id", UUID(as_uuid=True), sa.ForeignKey("supplier_proposals.id"), nullable=True),
        sa.Column("recommendation_rationale", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "proposal_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("evaluation_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("supplier_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("technical_fit_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("cost_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("timeline_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("risk_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("weighted_total", sa.Numeric(5, 2), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("ai_assessment", JSONB(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
    )

    op.create_table(
        "contracts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("supplier_proposals.id"), nullable=False),
        sa.Column("supplier_name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("draft_content", JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("generation_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "contract_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("revision_request", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "approval_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("checkpoint_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), unique=True, nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_runs_thread_id", "workflow_runs", ["thread_id"])

    op.create_table(
        "workflow_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("node_name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_events_thread_id", "workflow_events", ["thread_id"])

    op.create_table(
        "workflow_model_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("procurement_id", UUID(as_uuid=True), sa.ForeignKey("procurements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_type", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_label", sa.String(), nullable=False),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False, server_default="0.3"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workflow_model_configs")
    op.drop_table("workflow_events")
    op.drop_table("workflow_runs")
    op.drop_table("approval_actions")
    op.drop_table("contract_revisions")
    op.drop_table("contracts")
    op.drop_table("proposal_scores")
    op.drop_table("evaluations")
    op.drop_foreign_key("fk_procurement_selected_proposal", "procurements")
    op.drop_table("supplier_proposals")
    op.drop_table("rfp_revisions")
    op.drop_table("rfps")
    op.drop_table("procurements")
    op.drop_table("users")
