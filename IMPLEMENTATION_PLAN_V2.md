# Presentation Studio — Implementation Plan v2

> **Project:** DeckStudio  
> **Domain:** https://deckstudio.karlekar.cloud  
> **Date:** 2026-03-10  
> **Status:** Revised — DeepAgents integration confirmed

---

## 1. Project Overview

Presentation Studio (DeckStudio) is a web application that generates structured presentation decks through a 5-agent AI pipeline with human-in-the-loop (HITL) checkpoints at each stage. Users fill out a form describing their presentation needs, then watch as five specialized agents sequentially extract insights, design the narrative arc, generate slides, build appendix content, and validate quality — with the ability to approve, edit, or reject at each checkpoint.

**Core value proposition:** Transform unstructured context and requirements into a fully structured, schema-compliant presentation deck with human oversight at every critical decision point.

**Key capabilities:**
- Intake form capturing presentation type, audience, tone, context, and source material
- 5-stage DeepAgents pipeline with HITL approval gates
- Real-time pipeline status tracking via polling
- Editable slide gallery with drag-and-drop reordering
- Versioned JSON export of approved decks
- Session history and deck versioning

---

## 2. Infrastructure & Deployment Plan

### Server Layout

```
/opt/deckstudio/
├── backend/                 # Python app + venv
│   ├── venv/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   └── ...
├── data/                    # Session data, exported decks
│   ├── sessions/            # Per-session state (SQLite checkpoints)
│   └── exports/             # Versioned JSON exports
└── logs/                    # Application logs

/var/www/deckstudio/         # Built frontend static files
├── index.html
├── assets/
└── ...
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name deckstudio.karlekar.cloud;

    ssl_certificate /etc/letsencrypt/live/deckstudio.karlekar.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/deckstudio.karlekar.cloud/privkey.pem;

    # Frontend static files
    root /var/www/deckstudio;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # Long timeout for agent operations
    }
}

server {
    listen 80;
    server_name deckstudio.karlekar.cloud;
    return 301 https://$host$request_uri;
}
```

### Systemd Service

```ini
[Unit]
Description=DeckStudio Backend
After=network.target

[Service]
Type=simple
User=deckstudio
WorkingDirectory=/opt/deckstudio/backend
ExecStart=/opt/deckstudio/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always
RestartSec=5
Environment=PYTHONPATH=/opt/deckstudio/backend

[Install]
WantedBy=multi-user.target
```

### SSL

- Certbot with nginx plugin: `certbot --nginx -d deckstudio.karlekar.cloud`
- Auto-renewal via certbot timer (already standard on most setups)

---

## 3. Technology Stack

### Backend
| Component | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| FastAPI | 0.115+ | API framework |
| DeepAgents | latest | Agent harness (wraps LangGraph) |
| LangGraph | latest (dep of DeepAgents) | State graph, checkpointing |
| LangChain | latest (dep of DeepAgents) | LLM abstractions |
| Pydantic | v2 | Schema validation, structured output |
| python-dotenv | latest | Environment management |
| aiofiles | latest | Async file I/O |
| uvicorn | latest | ASGI server |
| SQLite | built-in | Session checkpointing (via langgraph SqliteSaver) |

### Frontend
| Component | Version | Purpose |
|---|---|---|
| React | 18+ | UI framework |
| TypeScript | 5+ | Type safety |
| Vite | 5+ | Build tool |
| Tailwind CSS | 3+ | Styling |
| React Router | v6 | Client-side routing |
| Axios | latest | HTTP client |
| React Hook Form | latest | Form management |
| Zod | latest | Schema validation |
| Zustand | latest | State management |
| Lucide React | latest | Icons |
| React Hot Toast | latest | Notifications |
| Framer Motion | latest | Animations |

**All dependencies confirmed available.** No risk flags on the stack.

---

## 4. DeepAgents Architecture

### Architecture Decision: Orchestrator with Subagents

**Recommended approach:** A single **orchestrator agent** with 5 registered **subagents**, using `interrupt_on={"task": True}` on the orchestrator.

**Why this over 5 separate agents:**

1. **Single checkpointer** — one SqliteSaver manages the entire pipeline state, making resume/replay trivial
2. **Natural HITL flow** — the orchestrator calls `task("insight_extractor", ...)` and gets interrupted before delegation. The FastAPI layer inspects the pending tool call, surfaces it to the frontend, and on approval resumes the graph. This gives us exactly one interrupt point per stage.
3. **Simpler session management** — one LangGraph thread_id per session, one graph to invoke/resume
4. **Subagent isolation** — each subagent has its own system prompt, tools, and optional model override, so they remain specialized
5. **Built-in sequencing** — the orchestrator's system prompt defines the pipeline order; no external workflow engine needed

### Orchestrator Definition

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("/opt/deckstudio/data/sessions/checkpoints.db")

orchestrator = create_deep_agent(
    name="deck-orchestrator",
    model="anthropic:claude-sonnet-4-6",
    system_prompt="""You are a presentation deck orchestrator. Given user requirements,
    you coordinate 5 specialized agents in sequence:
    1. insight_extractor — extract core insights from context
    2. deck_architect — design narrative arc and outline
    3. slide_generator — generate all slides as structured JSON
    4. appendix_builder — generate appendix content
    5. quality_validator — validate schema compliance
    
    Call each agent using the task tool in order. Pass the output of each
    to the next. If quality_validator returns violations, call slide_generator
    again with the violations (max 3 retries). Return the final validated deck.""",
    
    tools=[],  # Only uses built-in `task` tool for subagent delegation
    
    interrupt_on={
        "task": True,  # Pause before EVERY subagent delegation for HITL
    },
    
    checkpointer=checkpointer,
    
    response_format=DeckEnvelope,  # Final output as structured Pydantic
    
    subagents=[
        {
            "name": "insight_extractor",
            "description": "Extracts core insights, themes, and key messages from provided context and source material",
            "system_prompt": INSIGHT_EXTRACTOR_PROMPT,
            "tools": [extract_insights_tool],
            "model": "anthropic:claude-sonnet-4-6",
        },
        {
            "name": "deck_architect",
            "description": "Designs deck archetype, narrative arc, section structure, and slide outline",
            "system_prompt": DECK_ARCHITECT_PROMPT,
            "tools": [design_outline_tool],
            "model": "anthropic:claude-sonnet-4-6",
        },
        {
            "name": "slide_generator",
            "description": "Generates full slide content as structured JSON matching the Slide schema",
            "system_prompt": SLIDE_GENERATOR_PROMPT,
            "tools": [generate_slides_tool],
            "model": "anthropic:claude-sonnet-4-6",
        },
        {
            "name": "appendix_builder",
            "description": "Generates appendix slides with supporting data, references, and backup material",
            "system_prompt": APPENDIX_BUILDER_PROMPT,
            "tools": [build_appendix_tool],
            "model": "anthropic:claude-sonnet-4-6",
        },
        {
            "name": "quality_validator",
            "description": "Validates all slides against schema constraints: key_points ≤ 5, evidence ≤ 3, metaphor = 1 sentence",
            "system_prompt": QUALITY_VALIDATOR_PROMPT,
            "tools": [validate_deck_tool],
            "model": "anthropic:claude-sonnet-4-6",
        },
    ],
)
```

### HITL Mechanics

When the orchestrator calls `task("insight_extractor", {"context": "...", "source_material": "..."})`, DeepAgents (via LangGraph's interrupt mechanism) pauses execution **before** the tool call is dispatched.

The state at this point contains:
- `state["messages"]` — full conversation history
- The pending tool call with `name="task"` and `args={"agent": "insight_extractor", "input": "..."}`

Our FastAPI backend:
1. Detects the interrupt via `graph.get_state(config)` — checks if `next` is non-empty (indicating a pause)
2. Extracts the pending tool call arguments to determine which stage is pending
3. Stores this as a "checkpoint" record in our session service
4. Serves it to the frontend via `GET /api/deck/{session_id}/status`

On **approve**: Resume the graph with `graph.invoke(None, config)` (or `Command(resume=...)` if editing the input)
On **reject**: Resume with modified input, or abort the pipeline entirely

### Custom Tools for Each Subagent

Each subagent's custom tool is a thin wrapper that structures the LLM's output:

```python
from langchain_core.tools import tool

@tool
def extract_insights(context: str, source_material: str = "") -> dict:
    """Extract core insights from the provided context and source material.
    Return structured insights including themes, key messages, and audience considerations."""
    # This tool is the "action" the agent decides to take.
    # The agent's LLM generates the insights; this tool just
    # formats/validates the output structure.
    # In practice, the LLM output IS the insight extraction.
    pass  # Tool body can be minimal — the agent's reasoning IS the work
```

**Important design note:** For this use case, the custom tools serve primarily as **structured output anchors**. The actual "work" is the LLM reasoning in each subagent. The tools exist so that:
1. We have a named action to interrupt on (if using per-agent HITL)
2. The output is structured and parseable
3. The orchestrator pattern with `interrupt_on={"task": True}` means we don't strictly need per-subagent tools for HITL — the orchestrator-level interrupt is sufficient

### Quality Validation Loop

The orchestrator's system prompt instructs it to:
1. Call `task("quality_validator", deck_json)`
2. If the validator returns violations, call `task("slide_generator", {"deck": deck_json, "violations": violations})` again
3. Repeat up to 3 times
4. The `interrupt_on={"task": True}` will fire on each retry, giving the human visibility into the loop

The quality validator subagent checks:
- `key_points` list length ≤ 5 per slide
- `evidence` list length ≤ 3 per slide
- `metaphor` field is exactly 1 sentence (no periods except terminal)
- `title` is a conclusion statement (heuristic: contains a verb, not a fragment)

---

## 5. Backend Architecture

### Application Structure

```
backend/
├── main.py                      # FastAPI app factory, startup/shutdown, middleware
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py              # Pydantic Settings (env-backed config)
├── schemas/
│   ├── input.py                 # DeckRequest, GenerateRequest
│   └── output.py                # Slide, Deck, DeckEnvelope, CheckpointStatus, etc.
├── agents/
│   ├── orchestrator.py          # Main orchestrator create_deep_agent() setup
│   ├── insight_extractor.py     # Subagent definition + system prompt + tools
│   ├── deck_architect.py        # Subagent definition + system prompt + tools
│   ├── slide_generator.py       # Subagent definition + system prompt + tools
│   ├── appendix_agent.py        # Subagent definition + system prompt + tools
│   └── quality_validator.py     # Subagent definition + system prompt + tools
├── services/
│   ├── session_service.py       # Session CRUD, state tracking, checkpoint management
│   └── file_service.py          # Deck export, versioned JSON file management
├── api/
│   └── routes/
│       ├── deck.py              # All /api/deck/* routes
│       └── health.py            # /api/health
```

### Session Management

Each `POST /api/deck/generate` creates a session:

```python
@dataclass
class Session:
    session_id: str              # UUID
    thread_id: str               # LangGraph thread_id (= session_id)
    status: PipelineStatus       # PENDING, RUNNING, AWAITING_APPROVAL, COMPLETED, FAILED
    current_stage: str           # insight_extractor | deck_architect | ...
    checkpoints: List[Checkpoint]
    created_at: datetime
    updated_at: datetime
    deck: Optional[DeckEnvelope] # Final deck once completed
    version: int                 # Increments on each edit/approval
```

Sessions are stored in-memory (dict) with SQLite checkpointing for the LangGraph state. For MVP, this is sufficient — sessions survive agent restarts via the checkpointer, and the in-memory dict is rebuilt from the checkpoint DB on startup.

### Pipeline Runner

The pipeline runs in a background asyncio task:

```python
async def run_pipeline(session_id: str, request: GenerateRequest):
    config = {"configurable": {"thread_id": session_id}}
    
    # Initial invocation
    input_message = format_user_request(request)
    result = await asyncio.to_thread(orchestrator.invoke, {"messages": [input_message]}, config)
    
    # After each interrupt, the graph pauses.
    # The session_service detects the pause via get_state()
    # and updates session status to AWAITING_APPROVAL.
    # Resume happens when the /approve endpoint calls:
    #   orchestrator.invoke(None, config)
```

The background task pattern:
1. `POST /generate` → creates session, spawns `asyncio.create_task(run_pipeline(...))`
2. Pipeline runs until first interrupt → task suspends (graph returns)
3. Session status → `AWAITING_APPROVAL`, checkpoint saved
4. Frontend polls `GET /status` → sees checkpoint
5. User approves → `POST /approve` → spawns new task to `orchestrator.invoke(None, config)`
6. Repeat until pipeline completes

### Error Handling

- Each pipeline stage wrapped in try/except
- On LLM error: session status → FAILED with error details
- On timeout (configurable, default 120s per stage): graceful abort
- On user reject: session status → REJECTED, pipeline halted (can restart from that checkpoint)

---

## 6. Frontend Architecture

### Route Structure

```
/                           → IntakePage (form)
/pipeline/:sessionId        → PipelinePage (status + HITL checkpoints)
/gallery/:sessionId         → GalleryPage (slide gallery + export)
```

### Component Tree

```
App
├── Layout
│   ├── Header (logo, nav)
│   └── Footer
├── IntakePage
│   ├── DeckTypeSelector (5 deck types as cards)
│   ├── AudienceInput
│   ├── ToneSelector
│   ├── ContextTextarea
│   ├── SourceMaterialUpload (text paste or file)
│   └── SubmitButton
├── PipelinePage
│   ├── PipelineProgress (5-step progress bar)
│   ├── StageCard (current stage details)
│   ├── CheckpointModal (approve/reject/edit)
│   │   ├── InsightReview (stage 1 checkpoint content)
│   │   ├── OutlineReview (stage 2 checkpoint content)
│   │   ├── SlidesReview (stage 3 checkpoint content)
│   │   ├── AppendixReview (stage 4 checkpoint content)
│   │   └── ValidationReport (stage 5 checkpoint content)
│   └── PipelineLog (scrolling log of agent actions)
└── GalleryPage
    ├── SlideCard (individual slide, editable)
    ├── SlideEditor (inline edit form)
    ├── SlideList (ordered list of SlideCards)
    ├── DeckSummary (title, type, audience, stats)
    ├── ExportButton (download versioned JSON)
    └── VersionHistory (list of versions)
```

### Zustand Store

```typescript
interface DeckStore {
  // Session
  sessionId: string | null;
  status: PipelineStatus;
  currentStage: string;
  
  // Pipeline
  checkpoints: Checkpoint[];
  currentCheckpoint: Checkpoint | null;
  
  // Deck
  deck: DeckEnvelope | null;
  
  // Actions
  createSession: (request: GenerateRequest) => Promise<void>;
  pollStatus: () => Promise<void>;
  approveCheckpoint: (checkpointId: string, edits?: any) => Promise<void>;
  rejectCheckpoint: (checkpointId: string, reason: string) => Promise<void>;
  updateSlide: (slideId: string, updates: Partial<Slide>) => Promise<void>;
  exportDeck: () => Promise<void>;
}
```

### Polling Strategy

```typescript
// In usePipelinePolling hook:
useEffect(() => {
  if (status === 'RUNNING' || status === 'AWAITING_APPROVAL') {
    const interval = setInterval(() => pollStatus(), 2000); // 2s polling
    return () => clearInterval(interval);
  }
}, [status]);
```

- Poll every 2 seconds while pipeline is active
- Stop polling when COMPLETED, FAILED, or AWAITING_APPROVAL (user action needed)
- Resume polling after approve/reject action
- Toast notifications on stage transitions

---

## 7. HITL Flow — Detailed Sequence

### Sequence Diagram (text)

```
User          Frontend              Backend (FastAPI)         DeepAgents/LangGraph
  |               |                       |                          |
  |--[Fill Form]->|                       |                          |
  |               |--POST /generate------>|                          |
  |               |<--{session_id}--------|                          |
  |               |                       |--invoke(orchestrator)--->|
  |               |                       |                          |--[LLM reasons]
  |               |                       |                          |--task("insight_extractor")
  |               |                       |                          |--INTERRUPT (pause)
  |               |                       |<--state w/ pending tool--|
  |               |                       |--[update session: AWAITING_APPROVAL, stage=insight_extractor]
  |               |--GET /status--------->|                          |
  |               |<--{status: AWAITING,  |                          |
  |               |    checkpoint: {      |                          |
  |               |      id, stage,       |                          |
  |               |      pending_input,   |                          |
  |               |      preview}}        |                          |
  |               |                       |                          |
  |<-[Show Modal]-|                       |                          |
  |--[Approve]--->|                       |                          |
  |               |--POST /approve------->|                          |
  |               |                       |--invoke(None, config)--->|
  |               |                       |                          |--[resume, dispatch task]
  |               |                       |                          |--[insight_extractor runs]
  |               |                       |                          |--[orchestrator gets result]
  |               |                       |                          |--task("deck_architect")
  |               |                       |                          |--INTERRUPT
  |               |                       |<--state w/ pending tool--|
  |               |                       |--[update session: stage=deck_architect]
  |               |--GET /status--------->|                          |
  |               |<--{next checkpoint}---|                          |
  |               |   ... repeat ...      |                          |
```

### Checkpoint Data Structure

```python
class Checkpoint(BaseModel):
    checkpoint_id: str          # UUID
    stage: str                  # Agent name
    stage_index: int            # 1-5
    status: Literal["pending", "approved", "rejected"]
    pending_input: dict         # What the agent is about to process
    preview: Optional[dict]     # Preview of output (for stages 2+ where prior output exists)
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution: Optional[Literal["approved", "rejected"]]
    edits: Optional[dict]       # User modifications before approval
```

### Approve with Edits

When approving, the user can optionally modify the data before it's passed to the next agent:

1. Frontend sends `POST /approve` with optional `edits` body
2. Backend modifies the pending tool call arguments with the edits
3. Resumes the graph with `Command(resume=edited_input)` (LangGraph's edit-on-resume)
4. The subagent receives the edited input instead of the original

### Reject Flow

On reject:
1. Frontend sends `POST /reject` with `reason`
2. Backend can either:
   - **Retry the stage:** Resume with modified prompt including rejection reason
   - **Halt the pipeline:** Mark session as REJECTED
3. For MVP: reject halts the pipeline. User can start a new session.

---

## 8. Test Strategy

### Backend Tests (23 files)

**Unit Tests (11 files):**
- `tests/unit/test_schemas_input.py` — Input schema validation, edge cases
- `tests/unit/test_schemas_output.py` — Output schema validation, constraints (key_points ≤ 5, etc.)
- `tests/unit/test_settings.py` — Config loading, defaults, env overrides
- `tests/unit/test_insight_extractor.py` — Prompt construction, tool definition
- `tests/unit/test_deck_architect.py` — Prompt construction, tool definition
- `tests/unit/test_slide_generator.py` — Prompt construction, tool definition
- `tests/unit/test_appendix_agent.py` — Prompt construction, tool definition
- `tests/unit/test_quality_validator.py` — Validation logic (pure function, no LLM)
- `tests/unit/test_session_service.py` — Session CRUD, state transitions
- `tests/unit/test_file_service.py` — Export logic, versioning
- `tests/unit/test_orchestrator.py` — Orchestrator setup, subagent registration

**Integration Tests (5 files):**
- `tests/integration/test_pipeline_flow.py` — Full pipeline with mocked LLM (interrupt/resume cycle)
- `tests/integration/test_checkpoint_approve.py` — Approve flow with state verification
- `tests/integration/test_checkpoint_reject.py` — Reject flow
- `tests/integration/test_quality_loop.py` — Validation failure → retry loop (max 3)
- `tests/integration/test_session_persistence.py` — Checkpoint save/restore across restarts

**E2E Tests (3 files):**
- `tests/e2e/test_generate_deck.py` — Full HTTP flow: generate → poll → approve × 5 → export
- `tests/e2e/test_edit_slide.py` — Edit a slide after pipeline completion
- `tests/e2e/test_export.py` — Export versioned JSON, verify structure

**Support files:**
- `pytest.ini` — Config, markers, async mode
- `requirements-test.txt` — pytest, pytest-asyncio, httpx, factory-boy, respx (mock HTTP)
- `tests/conftest.py` — Fixtures: test client, mock orchestrator, sample data
- `tests/factories.py` — factory_boy factories for Slide, Deck, DeckEnvelope

### Frontend Tests (35 files)

**Unit Tests (4 files):**
- `tests/unit/deckStore.test.ts` — Zustand store actions and state
- `tests/unit/deckApi.test.ts` — API client functions
- `tests/unit/validation.test.ts` — Zod schema validation
- `tests/unit/hooks.test.ts` — Custom hooks

**Component Tests (18 files):**
- One test file per significant component (DeckTypeSelector, CheckpointModal, SlideCard, SlideEditor, PipelineProgress, etc.)

**Page Tests (3 files):**
- `tests/pages/IntakePage.test.tsx`
- `tests/pages/PipelinePage.test.tsx`
- `tests/pages/GalleryPage.test.tsx`

**E2E Tests (3 files, Playwright):**
- `tests/e2e/full-flow.spec.ts` — Complete flow: intake → pipeline → gallery → export
- `tests/e2e/hitl-checkpoints.spec.ts` — HITL approve/reject interactions
- `tests/e2e/slide-editing.spec.ts` — Edit slides in gallery

**Support files:**
- `vitest.config.ts`, `playwright.config.ts`, `tests/setup.ts`
- `tests/mocks/` — 5 mock files (handlers, server, data, api, store)

### Test Approach

- **Mocked LLM for all tests** — No real API calls in CI. Use respx/httpx mocks for backend, MSW for frontend.
- **Golden output fixtures** — Pre-built deck JSON for each pipeline stage, used in integration tests
- **Quality validator has pure logic** — Can be tested without any mocking
- **Playwright E2E** — Run against a local dev server with mocked backend

---

## 9. Environment & Configuration

### Environment Variables (.env)

```bash
# LLM Provider
ANTHROPIC_API_KEY=sk-ant-...          # Primary LLM provider
OPENAI_API_KEY=sk-...                 # Optional fallback

# DeepAgents
DEEPAGENTS_MODEL=anthropic:claude-sonnet-4-6
DEEPAGENTS_CHECKPOINT_DB=/opt/deckstudio/data/sessions/checkpoints.db

# App
APP_ENV=production                    # development | production
APP_HOST=127.0.0.1
APP_PORT=8001
APP_LOG_LEVEL=info
APP_CORS_ORIGINS=https://deckstudio.karlekar.cloud

# Pipeline
PIPELINE_STAGE_TIMEOUT=120            # seconds per stage
PIPELINE_MAX_QUALITY_RETRIES=3
PIPELINE_MODEL_OVERRIDE=              # override model for all agents

# Export
EXPORT_DIR=/opt/deckstudio/data/exports
SESSION_DIR=/opt/deckstudio/data/sessions
```

### Settings (Pydantic Settings)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str = ""
    deepagents_model: str = "anthropic:claude-sonnet-4-6"
    deepagents_checkpoint_db: str = "./data/sessions/checkpoints.db"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8001
    app_log_level: str = "info"
    app_cors_origins: str = "http://localhost:5173"
    pipeline_stage_timeout: int = 120
    pipeline_max_quality_retries: int = 3
    export_dir: str = "./data/exports"
    session_dir: str = "./data/sessions"
    
    class Config:
        env_file = ".env"
```

---

## 10. Build & Deployment Steps

### Initial Setup (one-time)

```bash
# 1. Create system user
sudo useradd -r -s /bin/false deckstudio

# 2. Create directories
sudo mkdir -p /opt/deckstudio/{backend,data/{sessions,exports},logs}
sudo mkdir -p /var/www/deckstudio
sudo chown -R deckstudio:deckstudio /opt/deckstudio
sudo chown -R deckstudio:deckstudio /var/www/deckstudio

# 3. Backend setup
cd /opt/deckstudio/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Frontend build
cd /path/to/frontend/source
npm install
npm run build
cp -r dist/* /var/www/deckstudio/

# 5. SSL
sudo certbot --nginx -d deckstudio.karlekar.cloud

# 6. Nginx config
sudo cp deckstudio.nginx.conf /etc/nginx/sites-available/deckstudio
sudo ln -s /etc/nginx/sites-available/deckstudio /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 7. Systemd service
sudo cp deckstudio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable deckstudio
sudo systemctl start deckstudio
```

### Deploy Updates

```bash
# Backend
cd /opt/deckstudio/backend
git pull  # or copy files
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart deckstudio

# Frontend
cd /path/to/frontend/source
npm run build
sudo cp -r dist/* /var/www/deckstudio/
```

---

## 11. Risk Flags

| Risk | Severity | Mitigation |
|---|---|---|
| **LLM latency** — Each agent stage takes 10-30s, total pipeline may take 2-5 min | Medium | Polling with progress updates; generous timeouts; timeout per stage |
| **LLM output format** — Agent may not produce valid JSON for Slide schema | Medium | Pydantic `response_format` in DeepAgents enforces structure; quality validator as safety net; retry on parse failure |
| **Checkpoint DB corruption** — SQLite under concurrent writes | Low | Single-writer pattern (one pipeline per session); WAL mode |
| **Cost** — 5 agent calls per deck, each with substantial context | Medium | Track token usage; configurable model per stage (use haiku for validator) |
| **Session memory** — In-memory session dict lost on restart | Medium | Rebuild from checkpoint DB on startup; or migrate to Redis later |
| **HITL UX** — Users may not understand what they're approving | Medium | Rich preview rendering for each checkpoint type; clear labels and guidance |
| **Quality loop divergence** — Validator and generator may disagree infinitely | Low | Hard cap at 3 retries; on 4th failure, present to user with warnings |

---

## 12. File/Directory Layout

### Complete File List (111 files)

```
deckstudio/
├── README.md
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── .env.example
│   ├── pytest.ini
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── schemas/
│   │   ├── input.py
│   │   └── output.py
│   │
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── insight_extractor.py
│   │   ├── deck_architect.py
│   │   ├── slide_generator.py
│   │   ├── appendix_agent.py
│   │   └── quality_validator.py
│   │
│   ├── services/
│   │   ├── session_service.py
│   │   └── file_service.py
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── deck.py
│   │       └── health.py
│   │
│   └── tests/
│       ├── conftest.py
│       ├── factories.py
│       │
│       ├── unit/
│       │   ├── test_schemas_input.py
│       │   ├── test_schemas_output.py
│       │   ├── test_settings.py
│       │   ├── test_insight_extractor.py
│       │   ├── test_deck_architect.py
│       │   ├── test_slide_generator.py
│       │   ├── test_appendix_agent.py
│       │   ├── test_quality_validator.py
│       │   ├── test_session_service.py
│       │   ├── test_file_service.py
│       │   └── test_orchestrator.py
│       │
│       ├── integration/
│       │   ├── test_pipeline_flow.py
│       │   ├── test_checkpoint_approve.py
│       │   ├── test_checkpoint_reject.py
│       │   ├── test_quality_loop.py
│       │   └── test_session_persistence.py
│       │
│       └── e2e/
│           ├── test_generate_deck.py
│           ├── test_edit_slide.py
│           └── test_export.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── index.html
│   │
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   │
│   │   ├── types/
│   │   │   ├── deck.ts
│   │   │   └── api.ts
│   │   │
│   │   ├── api/
│   │   │   └── deckApi.ts
│   │   │
│   │   ├── store/
│   │   │   └── deckStore.ts
│   │   │
│   │   ├── hooks/
│   │   │   ├── usePipelinePolling.ts
│   │   │   ├── useCheckpoint.ts
│   │   │   └── useDeckExport.ts
│   │   │
│   │   ├── pages/
│   │   │   ├── IntakePage.tsx
│   │   │   ├── PipelinePage.tsx
│   │   │   └── GalleryPage.tsx
│   │   │
│   │   └── components/
│   │       ├── layout/
│   │       │   ├── Header.tsx
│   │       │   ├── Footer.tsx
│   │       │   └── Layout.tsx
│   │       │
│   │       ├── intake/
│   │       │   ├── DeckTypeSelector.tsx
│   │       │   ├── AudienceInput.tsx
│   │       │   ├── ToneSelector.tsx
│   │       │   ├── ContextTextarea.tsx
│   │       │   ├── SourceMaterialUpload.tsx
│   │       │   └── SubmitButton.tsx
│   │       │
│   │       ├── pipeline/
│   │       │   ├── PipelineProgress.tsx
│   │       │   ├── StageCard.tsx
│   │       │   ├── CheckpointModal.tsx
│   │       │   ├── InsightReview.tsx
│   │       │   ├── OutlineReview.tsx
│   │       │   ├── SlidesReview.tsx
│   │       │   ├── AppendixReview.tsx
│   │       │   ├── ValidationReport.tsx
│   │       │   └── PipelineLog.tsx
│   │       │
│   │       ├── gallery/
│   │       │   ├── SlideCard.tsx
│   │       │   ├── SlideEditor.tsx
│   │       │   ├── SlideList.tsx
│   │       │   └── DeckSummary.tsx
│   │       │
│   │       └── export/
│   │           ├── ExportButton.tsx
│   │           └── VersionHistory.tsx
│   │
│   └── tests/
│       ├── setup.ts
│       │
│       ├── mocks/
│       │   ├── handlers.ts
│       │   ├── server.ts
│       │   ├── data.ts
│       │   ├── api.ts
│       │   └── store.ts
│       │
│       ├── unit/
│       │   ├── deckStore.test.ts
│       │   ├── deckApi.test.ts
│       │   ├── validation.test.ts
│       │   └── hooks.test.ts
│       │
│       ├── components/
│       │   ├── Header.test.tsx
│       │   ├── DeckTypeSelector.test.tsx
│       │   ├── AudienceInput.test.tsx
│       │   ├── ToneSelector.test.tsx
│       │   ├── ContextTextarea.test.tsx
│       │   ├── SourceMaterialUpload.test.tsx
│       │   ├── SubmitButton.test.tsx
│       │   ├── PipelineProgress.test.tsx
│       │   ├── StageCard.test.tsx
│       │   ├── CheckpointModal.test.tsx
│       │   ├── InsightReview.test.tsx
│       │   ├── OutlineReview.test.tsx
│       │   ├── SlidesReview.test.tsx
│       │   ├── SlideCard.test.tsx
│       │   ├── SlideEditor.test.tsx
│       │   ├── SlideList.test.tsx
│       │   ├── ExportButton.test.tsx
│       │   └── VersionHistory.test.tsx
│       │
│       ├── pages/
│       │   ├── IntakePage.test.tsx
│       │   ├── PipelinePage.test.tsx
│       │   └── GalleryPage.test.tsx
│       │
│       └── e2e/
│           ├── full-flow.spec.ts
│           ├── hitl-checkpoints.spec.ts
│           └── slide-editing.spec.ts
│
└── deploy/
    ├── deckstudio.nginx.conf
    ├── deckstudio.service
    └── deploy.sh
```

**File count:** 16 backend app + 23 backend tests + 36 frontend app + 35 frontend tests + 1 README = **111 files** ✓ (+ 3 deploy support files)
