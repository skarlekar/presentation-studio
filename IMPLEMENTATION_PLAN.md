# Presentation Studio — Implementation Plan

**App Name:** Presentation Studio (DeckStudio)
**Domain:** https://deckstudio.karlekar.cloud
**Date:** 2026-03-10
**Status:** DRAFT — Awaiting human review before implementation

---

## 1. Project Overview

### What It Does

Presentation Studio is a web application that generates structured presentation decks from user-provided context using a 5-agent AI pipeline. Each agent performs a discrete task (extract insights → architect deck → generate slides → build appendix → validate quality), and the user reviews/approves output at **human-in-the-loop (HITL) checkpoints** between each stage.

### Key User Flows

1. **Intake** — User fills out a form (topic, audience, tone, slide count, optional source material upload) and submits to start generation.
2. **Pipeline Monitoring** — Frontend polls for status. At each HITL checkpoint, a modal appears showing the agent's output. User can approve, reject (with feedback), or edit inline.
3. **Gallery Review** — Once all agents complete, slides appear as editable cards. User can reorder, edit content, tweak key points.
4. **Export** — User previews the final JSON deck, views version history, and exports.

### Deployment Target

Single Linux server (srv1453358), already running nginx. Backend served via uvicorn on port 8001 behind nginx reverse proxy. Frontend built as static files served directly by nginx. SSL via certbot/Let's Encrypt.

---

## 2. Infrastructure & Deployment Plan

### Server Layout

| Component | Location | Served By |
|---|---|---|
| Frontend (built static) | `/var/www/deckstudio/` | nginx directly |
| Backend (FastAPI + agents) | `/opt/deckstudio/backend/` | uvicorn → systemd, proxied by nginx |
| Session data (file persistence) | `/opt/deckstudio/data/sessions/` | Backend reads/writes |
| Uploaded source materials | `/opt/deckstudio/data/uploads/` | Backend reads/writes |
| Logs | `/var/log/deckstudio/` | journald + file rotation |

### nginx Virtual Host

```nginx
server {
    listen 80;
    server_name deckstudio.karlekar.cloud;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name deckstudio.karlekar.cloud;

    ssl_certificate     /etc/letsencrypt/live/deckstudio.karlekar.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/deckstudio.karlekar.cloud/privkey.pem;

    # Frontend static files
    root /var/www/deckstudio;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;  # SPA fallback
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # Long timeout for agent processing
        proxy_send_timeout 300s;
        client_max_body_size 20M;  # Source material uploads
    }
}
```

### systemd Service — Backend

```ini
# /etc/systemd/system/deckstudio-backend.service
[Unit]
Description=DeckStudio Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/deckstudio/backend
EnvironmentFile=/opt/deckstudio/backend/.env
ExecStart=/opt/deckstudio/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Note:** `--workers 2` is sufficient for a single-user/low-traffic tool. Each worker can handle multiple concurrent async requests. If LangGraph agent calls block the event loop, consider bumping to 4 workers or using `run_in_executor` for CPU-bound LLM pre/post-processing.

### DNS & SSL

1. Add A record: `deckstudio.karlekar.cloud → <server IP>` (or CNAME if using existing domain)
2. After nginx config is in place: `sudo certbot --nginx -d deckstudio.karlekar.cloud`
3. Certbot auto-renewal via its systemd timer (already standard on most setups)

---

## 3. Technology Decisions & Rationale

### Frontend Stack — ✅ All Confirmed

| Library | Purpose | Verdict |
|---|---|---|
| React 18+ / TypeScript | UI framework | ✅ Standard, no concerns |
| Tailwind CSS | Utility-first styling | ✅ Fast iteration |
| React Router v6 | Tab navigation (hash or path-based) | ✅ Standard |
| Axios | HTTP client for API calls | ✅ Better than fetch for interceptors, retries |
| React Hook Form + Zod | Form management + validation | ✅ Excellent pairing |
| Lucide React | Icon library | ✅ Lightweight, tree-shakeable |
| React Hot Toast | Notifications | ✅ Simple, effective |
| Framer Motion | Animations (slide transitions, modal entry) | ✅ Nice UX polish |
| Zustand | Global state management | ✅ Lightweight, no boilerplate vs Redux |

### Backend Stack — ✅ With One Critical Flag

| Library | Purpose | Verdict |
|---|---|---|
| Python 3.11+ | Runtime | ✅ Required for LangGraph |
| FastAPI | API framework | ✅ Async-native, Pydantic integration |
| Pydantic v2 | Schema validation | ✅ Required by FastAPI |
| LangChain | LLM abstraction | ✅ Provider flexibility |
| **LangGraph** | Agent orchestration with HITL | ✅ **Replaces "DeepAgents"** — see §4 |
| python-dotenv | Config loading | ✅ Standard |
| aiofiles | Async file I/O for session persistence | ✅ Needed for non-blocking file ops |
| uvicorn | ASGI server | ✅ Standard |

### ⚠️ Critical Flag: "DeepAgents" Does Not Exist

The original spec references `langchain-ai/deepagents`. **This package does not exist** as a published PyPI or GitHub package. There is no `pip install deepagents` or `langchain-deepagents`.

**Resolution:** Use **LangGraph** (`langgraph` on PyPI, `langchain-ai/langgraph` on GitHub). LangGraph is the official LangChain library for building stateful, multi-actor agent workflows with:
- Graph-based node execution
- Built-in **checkpointing** (persistence of graph state)
- Native **HITL** via `interrupt_before` / `interrupt_after` on nodes
- Ability to resume from checkpoints after human review

This is exactly what the spec needs. No functionality is lost; LangGraph is the correct tool.

### Testing Stack — ✅ All Confirmed

All listed testing libraries are real, current, and appropriate for their roles. No flags.

---

## 4. LangGraph Architecture — 5-Agent Pipeline with HITL

### Graph Design

```
START
  │
  ▼
┌─────────────────────┐
│ InsightExtractorAgent│ ──→ interrupt_after ──→ HITL: "Confirm core insights"
└─────────────────────┘
  │ (approved)
  ▼
┌─────────────────────┐
│ DeckArchitectAgent   │ ──→ interrupt_after ──→ HITL: "Confirm deck outline"
└─────────────────────┘
  │ (approved)
  ▼
┌─────────────────────┐
│ SlideGeneratorAgent  │ ──→ interrupt_after ──→ HITL: "Review generated slides"
└─────────────────────┘
  │ (approved)              ▲
  ▼                         │ (quality violations → loop back)
┌─────────────────────┐     │
│ AppendixAgent        │ ──→ interrupt_after ──→ HITL: "Confirm appendix content"
└─────────────────────┘
  │ (approved)
  ▼
┌─────────────────────┐
│ QualityValidatorAgent│ ──→ conditional edge:
└─────────────────────┘       ├─ PASS → END
                              └─ FAIL → SlideGeneratorAgent (with violation feedback)
```

### LangGraph Implementation Approach

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # or SqliteSaver for persistence

# State schema
class DeckPipelineState(TypedDict):
    request: DeckRequest
    insights: Optional[list[str]]
    outline: Optional[DeckOutline]
    slides: Optional[list[Slide]]
    appendix: Optional[Appendix]
    validation_result: Optional[ValidationResult]
    quality_loop_count: int
    checkpoint_feedback: dict  # stores user edits/feedback per checkpoint

# Build graph
builder = StateGraph(DeckPipelineState)

builder.add_node("extract_insights", insight_extractor_node)
builder.add_node("architect_deck", deck_architect_node)
builder.add_node("generate_slides", slide_generator_node)
builder.add_node("build_appendix", appendix_node)
builder.add_node("validate_quality", quality_validator_node)

builder.set_entry_point("extract_insights")
builder.add_edge("extract_insights", "architect_deck")
builder.add_edge("architect_deck", "generate_slides")
builder.add_edge("generate_slides", "build_appendix")
builder.add_edge("build_appendix", "validate_quality")

# Conditional edge for quality validation
builder.add_conditional_edges(
    "validate_quality",
    route_quality_result,  # returns "generate_slides" or END
    {"generate_slides": "generate_slides", END: END}
)

# HITL checkpoints — interrupt AFTER each agent produces output
graph = builder.compile(
    checkpointer=MemorySaver(),  # or SqliteSaver for file persistence
    interrupt_after=["extract_insights", "architect_deck", "generate_slides", "build_appendix"]
)
```

### Checkpoint Persistence

Use `SqliteSaver` (backed by a per-session SQLite file in `/opt/deckstudio/data/sessions/{session_id}/checkpoint.db`) for durable checkpoint state. This means:
- Server restarts don't lose in-progress pipelines
- Each session has isolated state
- LangGraph handles serialization/deserialization of `DeckPipelineState`

### Resuming After HITL Approval

When user approves a checkpoint:
1. Backend loads the graph with the session's checkpointer
2. Optionally patches the state with user edits: `graph.update_state(config, {"insights": edited_insights})`
3. Calls `graph.invoke(None, config)` to resume from the last checkpoint
4. Graph runs until the next `interrupt_after` or `END`

When user rejects:
1. Backend patches state with rejection feedback
2. Re-runs the same node (re-invoke the graph from the current checkpoint)
3. The node sees the feedback in state and regenerates

### Quality Validation Loop

- `QualityValidatorAgent` checks all slides against Pydantic schema constraints (key_points ≤ 5, evidence ≤ 3, metaphor is exactly 1 sentence, etc.)
- If violations found: returns `"generate_slides"` from the routing function, with violation details in state
- Safety: cap quality loops at 3 iterations. After 3 failures, proceed to END with a warning flag in the response.

---

## 5. Backend Architecture

### FastAPI Application Structure

```
app/
├── main.py                 # FastAPI app, lifespan, CORS, router includes
├── config.py               # Settings via pydantic-settings (reads .env)
├── routers/
│   └── deck.py             # All /api/deck/* routes
├── schemas/
│   ├── deck.py             # DeckRequest, Slide, Deck, DeckEnvelope, etc.
│   ├── checkpoint.py       # CheckpointStatus, CheckpointAction
│   └── common.py           # EvidenceItem, IllustrationPrompt, Visual
├── agents/
│   ├── graph.py            # LangGraph graph definition + compilation
│   ├── state.py            # DeckPipelineState TypedDict
│   ├── nodes/
│   │   ├── insight_extractor.py
│   │   ├── deck_architect.py
│   │   ├── slide_generator.py
│   │   ├── appendix_builder.py
│   │   └── quality_validator.py
│   └── prompts/            # LLM prompt templates per agent
│       ├── insight_extractor.txt
│       ├── deck_architect.txt
│       ├── slide_generator.txt
│       ├── appendix_builder.txt
│       └── quality_validator.txt
├── services/
│   ├── session_manager.py  # In-memory registry + file persistence
│   ├── pipeline_runner.py  # Async task that runs LangGraph, updates session state
│   └── file_service.py     # Upload handling, export generation
└── models/
    └── session.py          # Session dataclass (id, status, state, history, timestamps)
```

### API Routes — Detailed

| Method | Path | Purpose | Notes |
|---|---|---|---|
| `POST` | `/api/deck/generate` | Start new pipeline | Accepts `DeckRequest` + optional file upload. Returns `{session_id}`. Spawns background task. |
| `GET` | `/api/deck/{session_id}/status` | Poll pipeline status | Returns `{status, current_agent, checkpoint?, progress_pct}`. Frontend polls this every 2–3s. |
| `POST` | `/api/deck/{session_id}/checkpoint/{checkpoint_id}/approve` | Approve HITL checkpoint | Optionally accepts edited data in body. Resumes LangGraph. |
| `POST` | `/api/deck/{session_id}/checkpoint/{checkpoint_id}/reject` | Reject HITL checkpoint | Accepts `{feedback: string}`. Re-runs current agent with feedback. |
| `GET` | `/api/deck/{session_id}` | Get full deck data | Returns current `DeckEnvelope` (all slides, appendix, metadata). |
| `PUT` | `/api/deck/{session_id}/slide/{slide_id}` | Update single slide | Accepts `SlideUpdateRequest`. For post-pipeline manual edits. |
| `POST` | `/api/deck/{session_id}/approve` | Final approval | Marks deck as "approved" — no more edits (optional workflow gate). |
| `POST` | `/api/deck/{session_id}/export` | Export deck | Returns deck JSON as downloadable file. |
| `GET` | `/api/deck/{session_id}/history` | Version history | Returns list of snapshots (one per checkpoint approval + manual edits). |

### Session Management

**In-Memory Registry:**
```python
# session_manager.py
sessions: dict[str, Session] = {}  # session_id → Session object
```

Each `Session` holds:
- `id: str` (UUID4)
- `status: Literal["running", "checkpoint", "completed", "failed"]`
- `current_agent: Optional[str]`
- `checkpoint: Optional[CheckpointInfo]` (agent name, label, data snapshot)
- `deck: Optional[DeckEnvelope]`
- `history: list[DeckSnapshot]` (versioned snapshots)
- `created_at`, `updated_at`: datetime
- `langgraph_config: dict` (thread_id for LangGraph checkpointer)

**File Persistence:**
- On every state change, serialize session to `/opt/deckstudio/data/sessions/{session_id}/session.json`
- LangGraph checkpoint DB at `/opt/deckstudio/data/sessions/{session_id}/checkpoint.db`
- On server restart, re-hydrate active sessions from disk

**TTL:** Sessions expire after 24 hours of inactivity. A background task (FastAPI lifespan or periodic `asyncio.create_task`) cleans up expired sessions and their disk artifacts.

### Background Task Execution

Pipeline runs must not block the request/response cycle:

```python
@router.post("/api/deck/generate")
async def generate_deck(request: DeckRequest, background_tasks: BackgroundTasks):
    session = session_manager.create_session(request)
    background_tasks.add_task(pipeline_runner.run, session)
    return {"session_id": session.id}
```

`pipeline_runner.run()` invokes `graph.ainvoke()` (async), catches `GraphInterrupt` exceptions to detect HITL pauses, and updates the session state accordingly.

**Important:** Use `asyncio.to_thread` or `run_in_executor` if any LangGraph/LangChain calls are synchronous and blocking.

---

## 6. Frontend Architecture

### Component Tree

```
App
├── Layout
│   ├── Header (logo, app name)
│   └── TabNavigation (Intake | Gallery | Export)
├── IntakePage (Tab 1)
│   ├── IntakeForm
│   │   ├── RequiredFields (context textarea, audience select, deck_type, slides count, tone, decision_inform_ask)
│   │   ├── OptionalFields (collapsible: source material upload, additional instructions)
│   │   └── SubmitButton
│   └── PipelineStatusBar (appears after submission, shows agent progress)
├── GalleryPage (Tab 2)
│   ├── PipelineProgress (top bar showing which agent is active)
│   ├── SlideCardGrid
│   │   └── SlideCard (repeated)
│   │       ├── SlideHeader (title, slide number)
│   │       ├── SlideBody (key points, evidence, metaphor, visual prompt)
│   │       └── SlideEditButton → opens inline editor
│   ├── SlideEditor (modal or inline expansion)
│   └── CheckpointModal (overlay during HITL pauses)
│       ├── CheckpointHeader (agent name, prompt: "Confirm core insights")
│       ├── CheckpointDataView (read-only or editable view of agent output)
│       ├── CheckpointFeedbackInput (for rejection feedback)
│       └── CheckpointActions (Approve / Reject buttons)
├── ExportPage (Tab 3)
│   ├── JsonPreview (formatted, syntax-highlighted deck JSON)
│   ├── VersionHistory (list of snapshots with timestamps, clickable to preview)
│   └── ExportButton (download JSON)
└── Shared
    ├── LoadingSpinner
    ├── ErrorBoundary
    └── Toast (via React Hot Toast)
```

### Zustand Store Shape

```typescript
interface DeckStudioStore {
  // Session
  sessionId: string | null;
  status: 'idle' | 'running' | 'checkpoint' | 'completed' | 'failed';
  currentAgent: string | null;
  error: string | null;

  // Pipeline
  checkpoint: {
    id: string;
    agentName: string;
    label: string;
    data: unknown;  // agent-specific output to review
  } | null;

  // Deck data
  deck: DeckEnvelope | null;
  history: DeckSnapshot[];

  // Active tab
  activeTab: 'intake' | 'gallery' | 'export';

  // Actions
  setActiveTab: (tab: string) => void;
  startGeneration: (request: DeckRequest) => Promise<void>;
  pollStatus: () => Promise<void>;
  approveCheckpoint: (checkpointId: string, edits?: unknown) => Promise<void>;
  rejectCheckpoint: (checkpointId: string, feedback: string) => Promise<void>;
  updateSlide: (slideId: string, update: SlideUpdateRequest) => Promise<void>;
  fetchDeck: () => Promise<void>;
  fetchHistory: () => Promise<void>;
  exportDeck: () => Promise<void>;
}
```

### Polling Strategy

After `startGeneration` returns a `session_id`:

1. Begin polling `GET /api/deck/{session_id}/status` every **2 seconds**
2. If `status === "checkpoint"`: stop polling, show `CheckpointModal` with checkpoint data
3. If `status === "running"`: continue polling, update progress indicator
4. If `status === "completed"`: stop polling, fetch full deck, switch to Gallery tab
5. If `status === "failed"`: stop polling, show error toast

**Implementation:** Use `useEffect` with `setInterval` inside GalleryPage (or a custom `usePipelinePoller` hook). Clear interval on unmount or terminal status.

**Optimization:** After user approves/rejects a checkpoint, immediately resume polling (don't wait for the next interval tick).

### Tab Navigation

Use React Router v6 with nested routes:
- `/` → redirect to `/intake`
- `/intake` → IntakePage
- `/gallery` → GalleryPage (disabled until session exists)
- `/export` → ExportPage (disabled until deck is completed)

Tabs are visually disabled (grayed out, not clickable) until prerequisites are met. This prevents users from navigating to an empty gallery.

---

## 7. Human-in-the-Loop (HITL) Flow — Detailed

### Sequence Diagram

```
User          Frontend              Backend (FastAPI)          LangGraph
 │               │                        │                       │
 │  Submit form  │                        │                       │
 │──────────────>│  POST /generate        │                       │
 │               │───────────────────────>│  create session       │
 │               │  {session_id}          │  spawn background     │
 │               │<───────────────────────│  task                 │
 │               │                        │──────────────────────>│ graph.ainvoke()
 │               │                        │                       │ run InsightExtractor
 │               │  GET /status (poll)    │                       │ interrupt_after fires
 │               │───────────────────────>│                       │
 │               │  {status: checkpoint,  │<──────────────────────│ GraphInterrupt
 │               │   checkpoint: {...}}   │                       │
 │               │<───────────────────────│                       │
 │               │                        │                       │
 │  Reviews modal│                        │                       │
 │  Clicks       │                        │                       │
 │  "Approve"    │                        │                       │
 │──────────────>│  POST /checkpoint/     │                       │
 │               │       .../approve      │                       │
 │               │───────────────────────>│  update_state (if edits)
 │               │  {ok}                  │  graph.ainvoke(None)  │
 │               │<───────────────────────│──────────────────────>│ resume → DeckArchitect
 │               │                        │                       │ ...next interrupt
 │               │  (resume polling)      │                       │
```

### Checkpoint Data Structure (API Response)

```json
{
  "status": "checkpoint",
  "current_agent": "InsightExtractorAgent",
  "checkpoint": {
    "id": "ckpt_abc123",
    "label": "Confirm core insights",
    "data": {
      "insights": [
        "AI is transforming healthcare through...",
        "Key regulatory concerns include..."
      ]
    },
    "editable": true,
    "schema_hint": "list of strings, each a core insight"
  }
}
```

### Approve with Edits

The checkpoint modal renders the data in an editable form. If the user modifies insights (adds, removes, rewrites), the edited data is sent with the approve call:

```json
POST /api/deck/{session_id}/checkpoint/ckpt_abc123/approve
{
  "edited_data": {
    "insights": [
      "AI is transforming healthcare through early detection...",
      "Regulatory frameworks are lagging behind adoption..."
    ]
  }
}
```

Backend calls `graph.update_state(config, {"insights": edited_insights})` before resuming.

### Reject with Feedback

```json
POST /api/deck/{session_id}/checkpoint/ckpt_abc123/reject
{
  "feedback": "Insights are too generic. Focus more on financial services use cases."
}
```

Backend injects feedback into state and re-invokes from the same node. The agent's prompt template includes a section: "The user provided this feedback on your previous output: {feedback}. Revise accordingly."

### Timeout Handling

If a user doesn't respond to a checkpoint within **1 hour**, the session remains paused. After **24 hours**, the session is cleaned up. The frontend shows a "Session expired" message if it tries to resume a cleaned-up session.

---

## 8. Test Strategy

### Backend Testing

**Framework:** pytest + pytest-asyncio + httpx (async test client for FastAPI)

**Coverage Target:** ≥ 85% line coverage (pytest-cov)

| Test Category | What to Test | Tools |
|---|---|---|
| **Unit — Schemas** | Pydantic model validation (field constraints, max lengths, enum values) | pytest, factory-boy, faker |
| **Unit — Agents** | Each agent node function in isolation (mock LLM calls, verify state transforms) | pytest-mock, respx (mock HTTP to OpenAI) |
| **Unit — Services** | Session manager CRUD, file service, pipeline runner | pytest-asyncio, tmp_path fixture |
| **Integration — API** | Full request/response cycle for each route | httpx.AsyncClient, pytest-asyncio |
| **Integration — Pipeline** | End-to-end pipeline with mocked LLM (all 5 agents, HITL approve/reject) | LangGraph with mock LLM, pytest-timeout |
| **Quality Loop** | QualityValidator detects violation → routes back to SlideGenerator → max 3 loops | Specific test with crafted invalid slides |

**Key Test Scenarios:**
1. Happy path: generate → approve all 5 checkpoints → completed
2. Reject at checkpoint 2 → re-run DeckArchitect with feedback → approve → continue
3. Edit data at checkpoint 3 → updated slides reflect edits
4. Quality validation fails → loops to SlideGenerator → passes on retry
5. Quality validation fails 3 times → exits with warning
6. Session TTL expiry
7. Concurrent sessions don't interfere
8. Invalid DeckRequest (slides < 3, > 50, missing required fields)
9. Slide update after pipeline completion
10. Export generates valid JSON

### Frontend Testing

**Framework:** Vitest + React Testing Library + MSW (mock service worker) + Playwright

**Coverage Target:** ≥ 80% line coverage (c8/istanbul)

| Test Category | What to Test | Tools |
|---|---|---|
| **Unit — Components** | Each component renders correctly, handles props | Vitest, RTL, @testing-library/jest-dom |
| **Unit — Store** | Zustand store actions produce correct state | Vitest (test store in isolation) |
| **Unit — Forms** | IntakeForm validation (required fields, Zod schema errors) | RTL, @testing-library/user-event |
| **Integration — Polling** | Status polling starts/stops correctly, checkpoint modal appears | MSW (mock API), Vitest with fake timers |
| **Integration — HITL** | Approve/reject flow updates store and UI | MSW, RTL |
| **E2E** | Full user journey: fill form → monitor → approve checkpoints → export | Playwright |

**Key Frontend Test Scenarios:**
1. IntakeForm: required field validation, Zod errors displayed
2. IntakeForm: successful submission → session created → tab switches to Gallery
3. GalleryPage: polling shows progress, transitions to checkpoint modal
4. CheckpointModal: displays correct data per agent, approve sends correct payload
5. CheckpointModal: reject sends feedback, new checkpoint appears after re-run
6. SlideCard: inline editing works, save calls PUT endpoint
7. ExportPage: JSON preview matches deck data, download triggers file save
8. Tab navigation: Gallery/Export disabled until prerequisites met
9. Error handling: API failure → toast notification
10. E2E: complete happy path from intake to export

---

## 9. Environment & Configuration

### Backend `.env` File

```bash
# /opt/deckstudio/backend/.env

# OpenAI (or other LLM provider)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o           # or gpt-4o-mini for cost savings during dev

# App
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=8001
LOG_LEVEL=info

# Session management
SESSION_TTL_HOURS=24
SESSION_DATA_DIR=/opt/deckstudio/data/sessions
UPLOAD_DIR=/opt/deckstudio/data/uploads
MAX_UPLOAD_SIZE_MB=20

# Quality validation
MAX_QUALITY_LOOPS=3

# CORS (allow the frontend origin)
CORS_ORIGINS=https://deckstudio.karlekar.cloud
```

### Frontend `.env` (build-time)

```bash
# Used during Vite build
VITE_API_BASE_URL=/api
VITE_APP_NAME=Presentation Studio
```

### Config Loading (Backend)

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    app_env: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8001
    log_level: str = "info"
    session_ttl_hours: int = 24
    session_data_dir: str = "/opt/deckstudio/data/sessions"
    upload_dir: str = "/opt/deckstudio/data/uploads"
    max_upload_size_mb: int = 20
    max_quality_loops: int = 3
    cors_origins: list[str] = ["https://deckstudio.karlekar.cloud"]

    class Config:
        env_file = ".env"
```

---

## 10. Build & Deployment Steps

### Prerequisites

- Python 3.11+ installed (or pyenv)
- Node.js 18+ installed (or nvm)
- nginx installed and running
- certbot installed
- DNS A record for `deckstudio.karlekar.cloud` pointing to server IP

### Ordered Deployment Sequence

```bash
# 1. Create directory structure
sudo mkdir -p /opt/deckstudio/backend
sudo mkdir -p /opt/deckstudio/data/{sessions,uploads}
sudo mkdir -p /var/www/deckstudio
sudo mkdir -p /var/log/deckstudio
sudo chown -R www-data:www-data /opt/deckstudio /var/www/deckstudio /var/log/deckstudio

# 2. Deploy backend
cd /opt/deckstudio/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with real OPENAI_API_KEY and other settings

# 3. Run backend tests
pytest --cov=app --cov-report=term-missing tests/

# 4. Build frontend
cd /path/to/frontend-source
npm ci
npm run build        # Vite outputs to dist/
sudo cp -r dist/* /var/www/deckstudio/

# 5. Configure nginx
sudo cp nginx/deckstudio.conf /etc/nginx/sites-available/deckstudio
sudo ln -s /etc/nginx/sites-available/deckstudio /etc/nginx/sites-enabled/
sudo nginx -t        # Validate config
sudo systemctl reload nginx

# 6. SSL certificate
sudo certbot --nginx -d deckstudio.karlekar.cloud

# 7. Install and start backend systemd service
sudo cp systemd/deckstudio-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable deckstudio-backend
sudo systemctl start deckstudio-backend

# 8. Verify
curl -s https://deckstudio.karlekar.cloud/api/health | jq .
# Should return {"status": "ok"}
```

### Health Check Endpoint

Add a simple `GET /api/health` route that returns `{"status": "ok", "version": "1.0.0"}` — useful for systemd `ExecStartPost` checks and uptime monitoring.

---

## 11. Risk Flags & Mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **"DeepAgents" package doesn't exist** | 🔴 Critical | Use LangGraph instead. Fully supports the required HITL + checkpointing. Already addressed in this plan. |
| 2 | **OpenAI API key required** | 🟡 Medium | Must be provisioned before deployment. Consider supporting multiple providers via LangChain's model abstraction (Anthropic, local models). |
| 3 | **LLM API costs** | 🟡 Medium | 5 agents × multiple LLM calls per deck. GPT-4o at ~$5-15/deck. Mitigate: use gpt-4o-mini for non-critical agents (appendix, quality validation). Add cost tracking. |
| 4 | **Long-running async tasks** | 🟡 Medium | A single deck generation can take 2–5 minutes. Background tasks via `asyncio.create_task`. Uvicorn workers must not be killed during processing. Set systemd `TimeoutStopSec=30` and handle SIGTERM gracefully. |
| 5 | **HITL session TTL management** | 🟡 Medium | Users may abandon sessions mid-pipeline. Implement 24h TTL with cleanup task. LangGraph checkpoint DBs accumulate — periodic cleanup required. |
| 6 | **No authentication** | 🟡 Medium | Spec doesn't mention auth. For a personal/demo tool, this is acceptable. For multi-user: add API key auth or OAuth. At minimum, session IDs are UUID4 (unguessable). |
| 7 | **Server memory with multiple concurrent sessions** | 🟢 Low | Each session holds full deck state in memory. For a personal tool, this is fine. For scale: move session store to Redis/SQLite. |
| 8 | **File upload security** | 🟡 Medium | Validate file types (PDF, TXT, DOCX only), enforce size limits (20MB), sanitize filenames, store outside web root. |
| 9 | **Quality validation infinite loop** | 🟢 Low | Cap at 3 iterations (configurable). After max loops, proceed with warning. |
| 10 | **LangGraph version compatibility** | 🟢 Low | Pin `langgraph` version in requirements.txt. The HITL API (`interrupt_before`/`interrupt_after`) is stable as of langgraph 0.2+. |
| 11 | **No WebSocket for real-time updates** | 🟢 Low | Polling every 2s is simple and sufficient for this use case. WebSocket would be an optimization for future versions. |

---

## 12. File/Directory Layout

### Full Project Tree

```
/opt/deckstudio/
├── backend/
│   ├── .venv/                          # Python virtual environment
│   ├── .env                            # Environment variables (not in git)
│   ├── .env.example                    # Template for .env
│   ├── requirements.txt                # Pinned Python dependencies
│   ├── pyproject.toml                  # Project metadata, tool configs
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app, lifespan, CORS, routers
│   │   ├── config.py                   # Pydantic Settings
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── deck.py                 # All /api/deck/* routes
│   │   │   └── health.py               # GET /api/health
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── deck.py                 # DeckRequest, Slide, Deck, DeckEnvelope, SlideUpdateRequest
│   │   │   ├── checkpoint.py           # CheckpointStatus, CheckpointAction, CheckpointResponse
│   │   │   └── common.py              # EvidenceItem, IllustrationPrompt, Visual, Appendix
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py                # LangGraph StateGraph definition + compilation
│   │   │   ├── state.py                # DeckPipelineState TypedDict
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── insight_extractor.py
│   │   │   │   ├── deck_architect.py
│   │   │   │   ├── slide_generator.py
│   │   │   │   ├── appendix_builder.py
│   │   │   │   └── quality_validator.py
│   │   │   └── prompts/
│   │   │       ├── insight_extractor.txt
│   │   │       ├── deck_architect.txt
│   │   │       ├── slide_generator.txt
│   │   │       ├── appendix_builder.txt
│   │   │       └── quality_validator.txt
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── session_manager.py      # Session CRUD, in-memory + file persistence
│   │   │   ├── pipeline_runner.py      # Async pipeline execution, HITL coordination
│   │   │   └── file_service.py         # File upload handling, export generation
│   │   └── models/
│   │       ├── __init__.py
│   │       └── session.py              # Session dataclass
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Fixtures: test client, mock LLM, temp dirs
│   │   ├── factories.py                # factory-boy factories for test data
│   │   ├── unit/
│   │   │   ├── test_schemas.py
│   │   │   ├── test_session_manager.py
│   │   │   ├── test_file_service.py
│   │   │   └── test_agents/
│   │   │       ├── test_insight_extractor.py
│   │   │       ├── test_deck_architect.py
│   │   │       ├── test_slide_generator.py
│   │   │       ├── test_appendix_builder.py
│   │   │       └── test_quality_validator.py
│   │   └── integration/
│   │       ├── test_api_routes.py
│   │       ├── test_pipeline_e2e.py
│   │       └── test_hitl_flow.py
│   └── systemd/
│       └── deckstudio-backend.service
├── data/
│   ├── sessions/                       # Per-session directories
│   │   └── {session_id}/
│   │       ├── session.json            # Serialized session state
│   │       └── checkpoint.db           # LangGraph SQLite checkpoint
│   └── uploads/                        # Uploaded source materials
│       └── {session_id}/
│           └── {filename}
└── nginx/
    └── deckstudio.conf                 # nginx vhost config

/var/www/deckstudio/                    # Built frontend (Vite output)
├── index.html
├── assets/
│   ├── index-{hash}.js
│   └── index-{hash}.css
└── favicon.ico
```

### Frontend Source Tree (Development — NOT deployed)

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── .env                                # VITE_API_BASE_URL=/api
├── public/
│   └── favicon.ico
├── src/
│   ├── main.tsx                        # React entry point
│   ├── App.tsx                         # Router + Layout
│   ├── api/
│   │   ├── client.ts                   # Axios instance with base URL
│   │   └── deck.ts                     # API functions (generateDeck, getStatus, etc.)
│   ├── store/
│   │   └── useDeckStore.ts             # Zustand store
│   ├── hooks/
│   │   ├── usePipelinePoller.ts        # Polling hook
│   │   └── useTabGuard.ts             # Prevent navigation to locked tabs
│   ├── pages/
│   │   ├── IntakePage.tsx
│   │   ├── GalleryPage.tsx
│   │   └── ExportPage.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   └── TabNavigation.tsx
│   │   ├── intake/
│   │   │   ├── IntakeForm.tsx
│   │   │   ├── RequiredFields.tsx
│   │   │   ├── OptionalFields.tsx
│   │   │   └── SourceUpload.tsx
│   │   ├── gallery/
│   │   │   ├── PipelineProgress.tsx
│   │   │   ├── SlideCardGrid.tsx
│   │   │   ├── SlideCard.tsx
│   │   │   └── SlideEditor.tsx
│   │   ├── checkpoint/
│   │   │   ├── CheckpointModal.tsx
│   │   │   ├── CheckpointDataView.tsx
│   │   │   └── CheckpointActions.tsx
│   │   ├── export/
│   │   │   ├── JsonPreview.tsx
│   │   │   ├── VersionHistory.tsx
│   │   │   └── ExportButton.tsx
│   │   └── shared/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   ├── types/
│   │   ├── deck.ts                     # TypeScript types mirroring Pydantic schemas
│   │   └── api.ts                      # API response types
│   └── utils/
│       └── formatting.ts              # Date formatting, JSON pretty-print, etc.
├── tests/
│   ├── setup.ts                        # Vitest setup (MSW server, jest-dom matchers)
│   ├── mocks/
│   │   ├── handlers.ts                 # MSW request handlers
│   │   └── data.ts                     # Mock deck/slide data
│   ├── unit/
│   │   ├── components/
│   │   │   ├── IntakeForm.test.tsx
│   │   │   ├── SlideCard.test.tsx
│   │   │   ├── CheckpointModal.test.tsx
│   │   │   └── ExportButton.test.tsx
│   │   └── store/
│   │       └── useDeckStore.test.ts
│   └── e2e/
│       ├── playwright.config.ts
│       └── specs/
│           ├── intake.spec.ts
│           ├── pipeline-flow.spec.ts
│           └── export.spec.ts
└── playwright.config.ts
```

---

## Summary of Key Decisions

1. **LangGraph replaces "DeepAgents"** — the specified package doesn't exist; LangGraph provides identical capabilities.
2. **`interrupt_after`** on each of the first 4 agent nodes for HITL checkpoints.
3. **`SqliteSaver`** for durable LangGraph checkpoint persistence (survives restarts).
4. **Polling (not WebSocket)** for frontend status updates — simpler, sufficient for this use case.
5. **Background tasks** via FastAPI `BackgroundTasks` / `asyncio.create_task` for pipeline execution.
6. **No auth** for v1 (personal tool). Session UUIDs provide basic protection.
7. **Quality loop capped at 3** to prevent infinite cycling.
8. **24-hour session TTL** with periodic cleanup.

---

*This plan is ready for human review. No implementation should begin until approved.*
