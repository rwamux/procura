# Procura

AI-assisted procurement workflow platform. Procura guides a procurement through four sequential stages — RFP generation, supplier proposal intake, evaluation, and contract drafting — each backed by a stateful LangGraph workflow with human-in-the-loop review.

Built as a showcase of agentic AI patterns: parallel fan-out execution, interrupt/resume, checkpoint-based replay, and real-time SSE streaming.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, asyncpg, SQLAlchemy 2 (async) |
| AI orchestration | LangGraph, LangChain, OpenRouter |
| Database | PostgreSQL (app data + LangGraph checkpoints) |
| Migrations | Alembic |
| Frontend | Next.js 15, React 19, Tailwind CSS, shadcn/ui |
| Observability | LangSmith tracing, structured JSON logging |
| Deployment | Railway |

---

## Architecture

### Workflow engine

Each procurement stage is a compiled LangGraph `StateGraph`. All four graphs share the same patterns:

- **PostgreSQL checkpointer** — every node write is checkpointed, enabling pause/resume and time-travel replay from any prior checkpoint.
- **SSE streaming** — the `workflow_runner` service streams `node_start`, `node_end`, `stream_chunk`, and `interrupt` events to the frontend over Server-Sent Events as the graph executes.
- **Human-in-the-loop** — graphs pause at review nodes using LangGraph's `interrupt()`. The frontend receives an `interrupt` event, renders the review UI, then POSTs a decision which resumes the graph via `Command(resume=...)`.
- **Fan-out / fan-in** — proposal intake and evaluation use LangGraph's `Send()` primitive to spawn one subgraph branch per proposal, execute them in parallel, then converge at an aggregation node.
- **Per-workflow model config** — each workflow independently stores the chosen model ID and temperature, allowing different models for generation vs. evaluation.

### Request flow

```
Frontend
  │
  ├─ POST /workflows/{type}/start        Create WorkflowRun row, return thread_id
  │
  ├─ GET  /workflows/{type}/stream       Open SSE connection, execute graph
  │         ← node_start / node_end / stream_chunk events
  │         ← interrupt event (graph pauses at human_review node)
  │
  ├─ POST /workflows/{type}/resume       Send decision, graph resumes
  │         ← node_start / node_end / workflow_done events
  │
  └─ GET  /procurements/{id}/...         Fetch persisted results (RFP, scores, contract)
```

### Data model

```
Procurement
  ├── RFP                    (versioned; stores structured content as JSON)
  │     └── RFPRevision      (each revision request + AI re-draft)
  ├── SupplierProposal[]     (uploaded files or text; AI-extracted structured data)
  ├── Evaluation
  │     └── ProposalScore[]  (weighted scores + AI assessment per proposal)
  └── Contract               (versioned; sections generated in parallel)
        └── ContractRevision
```

`WorkflowRun` and `WorkflowEvent` tables record every run and every node execution, enabling the audit log export.

---

## Workflows

### 1 — RFP Generation

```
validate_prerequisites
  → load_requirements
  → generate_rfp ←──────────────────────────────────┐
  → validate_rfp_structure                           │
      ├─ [valid]     → human_review                  │
      │                  ├─ APPROVED        → persist_approved_rfp → END
      │                  ├─ REVISION        → store_revision ───────────┘
      │                  └─ REJECTED        → mark_rejected → END
      ├─ [invalid, retries remain] ──────────────────┘
      └─ [invalid, max retries]   → escalate_to_human → END
```

Generates a structured RFP (executive summary, scope, deliverables, evaluation criteria, timelines, legal notes). Validates the structure after generation and self-corrects up to 3 times before escalating.

### 2 — Proposal Intake

```
validate_prerequisites
  → load_proposals
  → fan_out (Send per proposal) ─────────────────────────────┐
      process_proposal (parallel)                             │
        ├─ read file (PDF / DOCX / text)                      │
        └─ AI structured extraction                          │
  → aggregate_extractions ←─────────────────────────────────┘
  → human_review
      ├─ APPROVED                → mark_intake_complete → END
      └─ reprocess_ids set       → load_proposals (retry failed)
```

Extracts structured procurement data from each uploaded proposal in parallel. The reviewer can approve or send specific proposals back for re-extraction.

### 3 — Evaluation

```
validate_prerequisites          (loads proposals, builds weights, creates Evaluation record)
  → load_extracted_proposals
  → fan_out (Send per proposal) ─────────────────────────────┐
      score_proposal (parallel)                               │
        └─ AI scores each criterion, computes weighted total  │
  → rank_proposals ←────────────────────────────────────────┘
  → generate_recommendation_rationale
  → human_review
      ├─ APPROVED               → finalize_selection → END
      └─ MANUAL_OVERRIDE        → apply_override → finalize_selection → END
```

Scores all proposals in parallel against the RFP's evaluation criteria with weighted scoring. Generates a narrative recommendation. The reviewer can accept or override the top-ranked supplier.

### 4 — Contract Drafting

```
validate_prerequisites
  → load_contract_context ←─────────────────────────────────┐
  → fan_out (Send per section) ──────────────────────────────┤
      generate_section (parallel)                            │
        scope / payment_terms / milestones /                 │
        legal_clauses / termination_clauses                  │
  → assemble_contract ←─────────────────────────────────────┘
  → validate_complete_contract
      ├─ [valid]     → human_review
      │                  ├─ APPROVED        → finalize_contract → END
      │                  ├─ REVISION        → store_revision → fan_out (retry sections)
      │                  └─ REJECTED        → mark_rejected → END
      ├─ [invalid, retries remain] → load_contract_context
      └─ [invalid, max retries]   → escalate → END
```

Generates all contract sections in parallel, then assembles and validates the complete contract. On revision, only the requested sections are regenerated.

---

## Project structure

```
procurai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py              JWT login / register
│   │   │   ├── procurements.py      CRUD + proposal upload + result viewers
│   │   │   └── workflows.py         Start / stream / resume / replay / audit log
│   │   ├── core/
│   │   │   └── auth.py              JWT dependency (standard + SSE)
│   │   ├── models/                  SQLAlchemy ORM models
│   │   ├── schemas/                 Pydantic request/response schemas
│   │   │   └── ai/                  Structured output schemas for LLM extraction
│   │   ├── services/
│   │   │   └── workflow_runner.py   SSE event loop, node timing, token tracking
│   │   ├── storage/
│   │   │   └── local.py             Local file storage (uploaded proposals)
│   │   ├── workflows/
│   │   │   ├── base.py              get_llm() — OpenRouter via langchain-openai
│   │   │   ├── checkpointer.py      AsyncPostgresSaver init/teardown
│   │   │   ├── rfp/
│   │   │   │   ├── graph.py         StateGraph definition
│   │   │   │   ├── nodes.py         Node functions
│   │   │   │   └── state.py         RFPState TypedDict
│   │   │   ├── proposal_intake/
│   │   │   ├── evaluation/
│   │   │   └── contract/
│   │   ├── config.py                Pydantic settings (normalises DB URLs)
│   │   ├── database.py              Async SQLAlchemy engine + session
│   │   ├── enums.py                 WorkflowType, ProcurementStage, etc.
│   │   ├── logging_config.py        JSON structured logging
│   │   └── main.py                  FastAPI app + lifespan
│   ├── alembic/                     Database migrations
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── railway.toml
└── frontend/
    ├── app/                         Next.js App Router pages
    ├── components/                  React components + shadcn/ui
    ├── next.config.ts               API proxy rewrite (→ API_URL env var)
    ├── package.json
    └── railway.toml
```

---

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, OPENROUTER_API_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at `http://localhost:3000`. All `/api/*` requests are proxied to the backend.

---

## Deployment

The backend deploys to **Railway**, the frontend to **Vercel**.

### Backend (Railway)

Add a Railway project with a **Postgres plugin** and one service connected to this repo.

In the service **Deploy → Custom Start Command**:
```
cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

In the service **Deploy → Healthcheck Path**: `/health`

Railpack detects Python via the root-level `requirements.txt` (which proxies to `backend/requirements.txt`).

**Environment variables**

| Variable | Source | Notes |
|---|---|---|
| `DATABASE_URL` | Railway Postgres plugin | Auto-injected. Accepts any `postgres://` format. |
| `SECRET_KEY` | Manual | Random string, min 32 chars. |
| `OPENROUTER_API_KEY` | Manual | From openrouter.ai |
| `APP_URL` | Manual | Vercel frontend URL |
| `LANGCHAIN_TRACING_V2` | Optional | `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | Optional | From smith.langchain.com |
| `LANGCHAIN_PROJECT` | Optional | Defaults to `procura` |

`DATABASE_URL_SYNC` does not need to be set — it is derived automatically from `DATABASE_URL`.

### Frontend (Vercel)

Connect the repo to Vercel and set **Root Directory** to `frontend`. Vercel auto-detects Next.js.

**Environment variables**

| Variable | Value |
|---|---|
| `API_URL` | Your Railway backend URL, e.g. `https://procura-backend.up.railway.app` |

---

## Key API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Get JWT token |
| `POST` | `/api/procurements` | Create procurement |
| `POST` | `/api/procurements/{id}/proposals` | Upload supplier proposal (file or text) |
| `POST` | `/api/procurements/{id}/workflows/{type}/start` | Start a workflow run |
| `GET` | `/api/procurements/{id}/workflows/{type}/stream` | SSE stream of node events |
| `POST` | `/api/procurements/{id}/workflows/{type}/resume` | Resume after human review |
| `GET` | `/api/procurements/{id}/workflows/{type}/checkpoints` | List checkpoints for replay |
| `POST` | `/api/procurements/{id}/workflows/{type}/replay` | Replay from a checkpoint |
| `GET` | `/api/procurements/{id}/workflows/audit-log` | Export full audit log (CSV) |
| `GET` | `/api/procurements/{id}/rfp` | Fetch latest RFP |
| `GET` | `/api/procurements/{id}/evaluation` | Fetch evaluation + scores |
| `GET` | `/api/procurements/{id}/contract` | Fetch latest contract |
