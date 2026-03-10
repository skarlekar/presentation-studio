# Presentation Studio — Task Breakdown V2

> **Project:** DeckStudio  
> **Date:** 2026-03-10  
> **Total Tasks:** 79  
> **Estimated Total Effort:** ~135-195 hours  
> **Reference:** IMPLEMENTATION_PLAN_V2.md, PROMPT_ARCHITECTURE.md  
> **Changes from V1:** +17 tasks filling all 13 gaps identified in gap analysis

---

## Change Log from V1

| Gap # | Gap Description | Resolution | New Task(s) |
|-------|----------------|------------|-------------|
| 🔴 1 | Presentation Architect Prompt not created | Added canonical prompt file + integration task | T-008, T-017a |
| 🔴 2 | ExportPage merged into Gallery instead of Tab 3 | Restored as dedicated Tab 3 | T-050a, T-050b, T-050c |
| 🔴 3 | No source material file processing | Added backend service for PDF/TXT/DOCX | T-022a |
| 🟡 4 | TabBar.tsx missing | Added explicit tab bar component | T-034a |
| 🟡 5 | Sub-editor components absorbed into SlideEditor | Broken out as 4 explicit components | T-045a, T-045b, T-045c, T-045d |
| 🟡 6 | AppendixSection.tsx missing | Added dedicated component | T-046a |
| 🟡 7 | AgentStatusBadge.tsx missing | Added component | T-038a |
| 🟡 8 | Session restore on restart | Added lifespan event task | T-029a |
| 🟡 9 | useDeckStatus.ts hook missing | Added hook | T-033a |
| 🟢 10 | Frontend .env/.env.example | Added task | T-006a |
| 🟢 11 | Python __init__.py files | Added task | T-002a |
| 🟢 12 | .gitignore | Added task | T-001a |
| 🟢 13 | AppShell.tsx not acknowledged | Added component (wraps Layout.tsx) | T-034b |

---

## Phase 1: Project Setup & Infrastructure (T-001 → T-007, +T-001a)

**T-001: Create project directory structure**
- Create `/opt/deckstudio/{backend,data/{sessions,exports},logs}`, `/var/www/deckstudio/`
- Create system user `deckstudio`
- Set permissions
- Est: 30 min

**T-001a: Create root .gitignore** ✨ NEW (Gap #12)
- Root-level `.gitignore` covering:
  - Python: `venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`
  - Node: `node_modules/`, `dist/`
  - Env: `.env`, `*.env.local`
  - Data: `data/`, `*.db`, `*.sqlite`
  - IDE: `.vscode/`, `.idea/`
  - Coverage: `coverage/`, `htmlcov/`
  - OS: `.DS_Store`, `Thumbs.db`
- Est: 15 min

**T-002: Initialize backend Python project**
- Create `backend/` directory structure: `config/`, `schemas/`, `agents/`, `services/`, `api/routes/`, `tests/`, `prompts/`
- Create `requirements.txt` with all dependencies: `fastapi`, `uvicorn`, `deepagents`, `langgraph`, `langchain-anthropic`, `pydantic[dotenv]`, `pydantic-settings`, `python-dotenv`, `aiofiles`, `pypdf`, `python-docx`
- Create `requirements-test.txt`: `pytest`, `pytest-asyncio`, `httpx`, `factory-boy`, `respx`
- Create Python venv, install deps
- Verify `from deepagents import create_deep_agent` works
- Est: 1 hr

**T-002a: Create all Python `__init__.py` files** ✨ NEW (Gap #11)
- Create `__init__.py` in every Python package directory:
  - `backend/__init__.py`
  - `backend/config/__init__.py`
  - `backend/schemas/__init__.py`
  - `backend/agents/__init__.py`
  - `backend/services/__init__.py`
  - `backend/api/__init__.py`
  - `backend/api/routes/__init__.py`
  - `backend/prompts/__init__.py`
  - `backend/tests/__init__.py`
- Each file: empty or contains `"""Package docstring."""`
- **Blocking:** Without these, all Python imports across packages will fail
- Est: 15 min

**T-003: Initialize frontend React/TypeScript project**
- `npm create vite@latest frontend -- --template react-ts`
- Install deps: `tailwindcss`, `postcss`, `autoprefixer`, `react-router-dom`, `axios`, `react-hook-form`, `@hookform/resolvers`, `zod`, `zustand`, `lucide-react`, `react-hot-toast`, `framer-motion`, `react-syntax-highlighter`
- Install dev deps: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@playwright/test`, `msw`, `jsdom`
- Configure Tailwind, TypeScript strict mode
- Est: 1 hr

**T-004: Create `.env.example` and config/settings.py**
- Write `.env.example` with all documented env vars (see Plan §9)
- Implement `config/settings.py` using `pydantic-settings.BaseSettings`
- Validate that settings load from `.env` file correctly
- Est: 1 hr

**T-005: Create deploy support files**
- `deploy/deckstudio.nginx.conf` — nginx config (see Plan §2)
- `deploy/deckstudio.service` — systemd unit (see Plan §2)
- `deploy/deploy.sh` — deployment script (backend + frontend build + copy)
- Est: 1 hr

**T-006: Configure Vite for production**
- `vite.config.ts` — proxy `/api` to backend in dev mode, build output to `dist/`
- `tailwind.config.ts` — content paths, theme extensions
- `tsconfig.json` — strict mode, path aliases
- Est: 30 min

**T-006a: Create frontend .env and .env.example** ✨ NEW (Gap #10)
- `frontend/.env.example` — documents all VITE_ variables:
  - `VITE_API_BASE_URL=http://localhost:8000`
  - `VITE_POLLING_INTERVAL_MS=2000`
  - `VITE_APP_TITLE=DeckStudio`
- `frontend/.env` — local dev defaults (gitignored)
- Est: 15 min

**T-007: Create README.md**
- Project overview, setup instructions (dev + prod), architecture summary, API docs link
- Est: 1 hr

---

## Phase 2: Backend — Core Schemas & Config (T-008 → T-011)

**T-008: Save the Presentation Architect Prompt** ✨ NEW (Gap #1) — 🔴 CRITICAL
- Create `backend/prompts/presentation_architect.txt` containing the FULL Presentation Architect Prompt verbatim
- This file is the **canonical source of truth** for the project's soul
- The prompt covers: ROLE, INPUT PLACEHOLDERS, HARD RULES, STEPs 1–14, FINAL OUTPUT
- **No summarization. No abbreviation. Every word matters.**
- All 5 agent system prompts will import and prepend this content
- See `PROMPT_ARCHITECTURE.md` for full details on how this file is used
- Est: 30 min

**T-009: Implement input schemas (schemas/input.py)**
- `GenerateRequest` — title, type (Literal 5 types), audience, tone, decision_inform_ask, context, source_material (optional), source_material_file (optional UploadFile), total_slides (optional)
- Field validators: type must be one of 5 Literal values, context min 50 chars, audience non-empty
- Est: 1 hr

**T-010: Implement output schemas (schemas/output.py)**
- `EvidenceItem(BaseModel)` — source, claim, data_point
- `Visual(BaseModel)` — type, description, data_reference
- `Slide(BaseModel)` — all fields per spec, validators: `key_points` max 5 (via `Field(max_length=5)`), `evidence` max 3, `metaphor` single sentence validator
- `AppendixSlide(BaseModel)`, `Appendix(BaseModel)` — appendix structures
- `Deck(BaseModel)` — full deck with all fields
- `DeckEnvelope(BaseModel)` — wrapper
- `Checkpoint(BaseModel)` — checkpoint_id, stage, stage_index, status, pending_input, preview, timestamps
- `SessionStatus(BaseModel)` — session_id, status enum, current_stage, checkpoints list, deck (optional)
- `PipelineStatus` enum — PENDING, RUNNING, AWAITING_APPROVAL, COMPLETED, FAILED, REJECTED
- Est: 2 hr

**T-011: Implement Insights and Outline intermediate schemas**
- `InsightSet(BaseModel)` — themes: List[str], key_messages: List[str], audience_considerations: List[str], constraints: List[str]
- `DeckOutline(BaseModel)` — archetype, narrative_arc, sections: List[SectionOutline], estimated_slides
- These are structured outputs for stages 1 and 2, used as checkpoint previews
- Est: 1 hr

**T-011a: Implement ValidationReport schema**
- `Violation(BaseModel)` — slide_id, field, constraint, actual_value, message
- `ValidationReport(BaseModel)` — valid: bool, violations: List[Violation], checked_at: datetime
- Est: 30 min

---

## Phase 3: Backend — DeepAgents Pipeline (T-012 → T-020, +T-017a)

**T-012: Implement prompt loader module (prompts/__init__.py)** ✨ REVISED
- Read `backend/prompts/presentation_architect.txt` at import time
- Store as module-level constant `PRESENTATION_ARCHITECT_PROMPT`
- Function `compose_system_prompt(agent_instructions: str) -> str` that returns `PRESENTATION_ARCHITECT_PROMPT + "\n\n" + agent_instructions`
- Validate file exists on load; raise `FileNotFoundError` with clear message if missing
- Est: 30 min

**T-013: Implement InsightExtractorAgent (agents/insight_extractor.py)**
- Import `compose_system_prompt` from prompts module
- Define agent-specific instructions: focus on STEP 1 only, output InsightSet schema
- System prompt = `compose_system_prompt(INSIGHT_EXTRACTOR_INSTRUCTIONS)`
- Define `extract_insights` tool using `@tool` decorator
- Export subagent config dict: `{"name": "insight_extractor", "description": ..., "system_prompt": ..., "tools": [...], "model": ...}`
- Set `response_format=InsightSet`
- Est: 2 hr

**T-014: Implement DeckArchitectAgent (agents/deck_architect.py)**
- Import `compose_system_prompt` from prompts module
- Define agent-specific instructions: focus on STEP 2 and STEP 3, output DeckOutline schema
- System prompt = `compose_system_prompt(DECK_ARCHITECT_INSTRUCTIONS)`
- Define `design_outline` tool
- Export subagent config dict
- Set `response_format=DeckOutline`
- Include deck archetype selection logic in prompt (Decision/Strategy/Update/TechDeep/Pitch patterns)
- Est: 2 hr

**T-015: Implement SlideGeneratorAgent (agents/slide_generator.py)**
- Import `compose_system_prompt` from prompts module
- Define agent-specific instructions: focus on STEPs 5–9 and 12–13, output full slides JSON
- System prompt = `compose_system_prompt(SLIDE_GENERATOR_INSTRUCTIONS)`
- Define `generate_slides` tool
- Export subagent config dict
- Set `response_format` for list of Slides
- Prompt must emphasize: title = conclusion statement, metaphor = 1 sentence, key_points ≤ 5, evidence ≤ 3
- Est: 2 hr

**T-016: Implement AppendixAgent (agents/appendix_agent.py)**
- Import `compose_system_prompt` from prompts module
- Define agent-specific instructions: focus on STEP 10, output appendix slides JSON
- System prompt = `compose_system_prompt(APPENDIX_BUILDER_INSTRUCTIONS)`
- Define `build_appendix` tool
- Export subagent config dict
- Set `response_format=Appendix`
- Est: 1.5 hr

**T-017: Implement QualityValidatorAgent (agents/quality_validator.py)**
- Import `compose_system_prompt` from prompts module
- Define agent-specific instructions: focus on STEP 9 field rules and output completeness rules
- System prompt = `compose_system_prompt(QUALITY_VALIDATOR_INSTRUCTIONS)`
- Define `validate_deck` tool — this one has **real logic** (not just LLM):
  - Check key_points length ≤ 5 per slide
  - Check evidence length ≤ 3 per slide
  - Check metaphor is single sentence (count periods, exclude abbreviations)
  - Check title is a conclusion statement (heuristic)
  - Return ValidationReport
- Can be hybrid: LLM for semantic checks (is title really a conclusion?), pure Python for structural checks
- Est: 2 hr

**T-017a: Verify Presentation Architect Prompt integration across all 5 agents** ✨ NEW (Gap #1 cont.)
- Write a dedicated test (`test_prompt_integration.py`) that:
  - Imports each agent's system prompt
  - Asserts each starts with the Presentation Architect Prompt text
  - Asserts each contains the agent-specific instructions appended after the base prompt
  - Asserts key phrases are present: "elite strategy consultant", "McKinsey / BCG style", "STEP 1", etc.
  - Logs first 100 chars of system prompt in debug mode
- **This test guards the soul of the project.** If any agent loses the base prompt, this test fails.
- Est: 1 hr

**T-018: Implement Orchestrator (agents/orchestrator.py)**
- Import all 5 subagent configs
- Initialize `SqliteSaver` checkpointer from settings
- Call `create_deep_agent()` with orchestrator system prompt, subagents list, `interrupt_on={"task": True}`
- Export the compiled graph
- Handle model override from settings
- Est: 2 hr

**T-019: Implement pipeline runner function**
- Async function `run_pipeline(session_id, request, session_service)`
- Format GenerateRequest into initial message for orchestrator
- Call `orchestrator.invoke()` with thread_id config
- After each return (interrupt or completion), update session via session_service
- Detect interrupt state: check `graph.get_state(config).next` — if non-empty, pipeline is paused
- Extract pending tool call info for checkpoint data
- Handle exceptions, update session to FAILED on error
- Est: 3 hr

**T-020: Implement checkpoint resume logic**
- Function `resume_pipeline(session_id, edits=None)`
- If edits provided: use `Command(resume=edited_data)` to modify the pending tool call
- If no edits: `orchestrator.invoke(None, config)` to resume as-is
- After resume, check if next interrupt or completion
- Update session state accordingly
- Est: 2 hr

**T-021: Implement quality validation retry loop handling**
- In orchestrator system prompt: instruct max 3 retries when validator fails
- Each retry triggers another `task("slide_generator", ...)` call → another interrupt
- Track retry count in session service
- On 4th failure: force completion with warnings attached to deck
- Est: 1.5 hr

---

## Phase 4: Backend — FastAPI Routes & Session Management (T-022 → T-029, +T-022a, +T-029a)

**T-022: Implement SessionService (services/session_service.py)**
- In-memory dict[str, Session] for active sessions
- Methods: `create_session()`, `get_session()`, `update_status()`, `add_checkpoint()`, `resolve_checkpoint()`, `set_deck()`, `get_all_sessions()`
- Session dataclass with all fields from Plan §5
- Thread-safe with asyncio Lock
- Est: 2 hr

**T-022a: Implement SourceMaterialService (services/source_material_service.py)** ✨ NEW (Gap #3) — 🔴 CRITICAL
- Extract text from uploaded files for use by InsightExtractorAgent
- Supported formats:
  - **PDF**: Use `pypdf` (PdfReader) to extract text from all pages
  - **TXT**: Read raw text with encoding detection (utf-8, latin-1 fallback)
  - **DOCX**: Use `python-docx` (Document) to extract paragraph text
- Validation:
  - Allowed MIME types: `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - Max file size: configurable via settings (default 10MB)
  - Reject unsupported types with clear error message
- Interface: `async def extract_text(file: UploadFile) -> str`
- Returns clean text string ready for LLM consumption
- Strips excessive whitespace, normalizes line endings
- Est: 2 hr

**T-023: Implement FileService (services/file_service.py)**
- `export_deck(session_id, deck)` → write versioned JSON to export dir
- `get_deck_versions(session_id)` → list versions
- `get_deck_version(session_id, version)` → read specific version
- Filename pattern: `{session_id}_v{version}_{timestamp}.json`
- Use `aiofiles` for async I/O
- Est: 1.5 hr

**T-024: Implement POST /api/deck/generate route**
- Validate `GenerateRequest` body
- If source_material_file provided: call SourceMaterialService to extract text, merge into source_material field
- Create session via session_service
- Spawn `asyncio.create_task(run_pipeline(...))`
- Return `{session_id, status: "PENDING"}`
- Est: 1 hr

**T-025: Implement GET /api/deck/{session_id}/status route**
- Return current session status, current_stage, checkpoints list
- If AWAITING_APPROVAL: include current checkpoint details with pending_input and preview
- Est: 1 hr

**T-026: Implement POST /api/deck/{session_id}/checkpoint/{checkpoint_id}/approve route**
- Accept optional `edits` body
- Resolve checkpoint as approved in session_service
- Call `resume_pipeline(session_id, edits)`
- Spawn background task for next pipeline segment
- Return updated status
- Est: 1.5 hr

**T-027: Implement POST /api/deck/{session_id}/checkpoint/{checkpoint_id}/reject route**
- Accept `reason` in body
- Resolve checkpoint as rejected
- For MVP: halt pipeline, set session to REJECTED
- Return updated status
- Est: 1 hr

**T-028: Implement deck CRUD routes**
- `GET /api/deck/{session_id}` — return full deck if completed
- `PUT /api/deck/{session_id}/slide/{slide_id}` — update single slide, increment version
- `POST /api/deck/{session_id}/approve` — mark deck as finally approved (post-editing)
- Est: 1.5 hr

**T-029: Implement export and history routes**
- `POST /api/deck/{session_id}/export` — trigger file_service.export_deck(), return download URL
- `GET /api/deck/{session_id}/history` — return version list from file_service
- Est: 1 hr

**T-029a: Implement session restore on server startup** ✨ NEW (Gap #8)
- FastAPI lifespan event (async context manager):
  - On startup: scan `SESSION_DIR` for all session JSON files
  - For each file: deserialize session data
  - Skip sessions in terminal state (`COMPLETED`, `FAILED`, `REJECTED`)
  - For non-terminal sessions: verify LangGraph checkpoint exists in SQLite
  - If valid checkpoint: restore session to in-memory dict, set status to `AWAITING_APPROVAL` (safe default — user must re-approve to continue)
  - If no valid checkpoint: mark as `FAILED` with reason "session lost on restart"
  - Log restore summary: "Restored X sessions, skipped Y terminal, Z failed"
- Est: 2 hr

**T-030: Implement health route and FastAPI app setup (main.py, api/routes/health.py)**
- `GET /api/health` — return `{status: "ok", version: "1.0.0"}`
- `main.py`: FastAPI app with CORS middleware, include routers, lifespan context manager (from T-029a)
- Startup: initialize session_service, verify checkpoint DB accessible, restore sessions
- CORS: allow configured origins
- Est: 1.5 hr

---

## Phase 5: Frontend — Foundation (T-031 → T-037, +T-033a, +T-034a, +T-034b)

**T-031: Implement TypeScript types (src/types/deck.ts, src/types/api.ts)**
- Mirror all backend Pydantic schemas as TypeScript interfaces
- `deck.ts`: Slide, Deck, DeckEnvelope, EvidenceItem, Visual, Appendix, InsightSet, DeckOutline, ValidationReport
- `api.ts`: GenerateRequest, GenerateResponse, SessionStatus, Checkpoint, PipelineStatus enum
- Est: 1.5 hr

**T-032: Implement API client (src/api/deckApi.ts)**
- Axios instance with base URL config (env-dependent via `VITE_API_BASE_URL`)
- Functions: `generateDeck()`, `getStatus()`, `approveCheckpoint()`, `rejectCheckpoint()`, `getDeck()`, `updateSlide()`, `approveDeck()`, `exportDeck()`, `getHistory()`
- Error handling wrapper with toast notifications
- Est: 1.5 hr

**T-033: Implement Zustand store (src/store/deckStore.ts)**
- Full store interface as defined in Plan §6
- Actions that call deckApi functions
- Polling integration (set interval in store action)
- Est: 2 hr

**T-033a: Implement useDeckStatus.ts hook** ✨ NEW (Gap #9)
- Custom hook: `useDeckStatus(sessionId: string)`
- Polls `GET /api/deck/{sessionId}/status` at configurable interval (`VITE_POLLING_INTERVAL_MS`)
- Returns typed object: `{ status, currentStage, checkpoints, activeAgent, isTerminal, isLoading, error }`
- Auto-stops polling on terminal states (COMPLETED, FAILED, REJECTED)
- Extracts `activeAgent` from checkpoint metadata for AgentStatusBadge
- Integrates with Zustand store for shared state
- Est: 1.5 hr

**T-034: Implement Layout components**
- `Header.tsx` — logo ("DeckStudio"), navigation (New Deck / Active Session)
- `Footer.tsx` — minimal footer
- `Layout.tsx` — wraps pages with Header/Footer, Toaster provider
- Est: 1 hr

**T-034a: Implement TabBar.tsx** ✨ NEW (Gap #4)
- Horizontal tab bar with 3 tabs: **Intake**, **Gallery**, **Export**
- Each tab: icon + label
- Active tab: highlighted with underline/background
- Disabled states:
  - Gallery tab disabled until pipeline reaches COMPLETED
  - Export tab disabled until deck exists
- Props: `activeTab`, `onTabChange`, `galleryEnabled`, `exportEnabled`
- Tests: renders 3 tabs, disabled states respected, click handlers fire correctly
- Est: 1.5 hr

**T-034b: Implement AppShell.tsx** ✨ NEW (Gap #13)
- App shell wrapper component (wraps Layout.tsx)
- Responsibilities:
  - Global error boundary
  - Toast/notification provider
  - TabBar integration at top level
  - Manages active tab state and routes accordingly
- Replaces direct Layout usage in App.tsx
- Children: renders active page based on tab state
- Est: 1 hr

**T-035: Implement App.tsx and routing**
- React Router v6 setup: `/`, `/pipeline/:sessionId`, `/gallery/:sessionId`, `/export/:sessionId`
- Wrap with AppShell (which wraps Layout)
- Est: 30 min

**T-036: Implement custom hooks**
- `usePipelinePolling.ts` — manages polling interval, auto-stop on terminal states
- `useCheckpoint.ts` — provides approve/reject handlers with optimistic updates
- `useDeckExport.ts` — handles export trigger and download
- Est: 1.5 hr

**T-037: Implement main.tsx and index.html**
- `main.tsx` — React root render with BrowserRouter
- `index.html` — HTML shell with Tailwind CSS, meta tags, favicon
- Est: 30 min

---

## Phase 6: Frontend — Components (T-038 → T-051, +T-038a, +T-045a-d, +T-046a, +T-050a-c)

**T-038: Implement IntakePage with form components**
- `IntakePage.tsx` — page container, React Hook Form + Zod validation, submit handler
- `DeckTypeSelector.tsx` — 5 deck type cards (Decision, Strategy, Update, Tech Deep Dive, Pitch) with icons, selectable
- `AudienceInput.tsx` — text input with label
- `ToneSelector.tsx` — dropdown or chip selector (Professional, Conversational, Technical, Executive, Inspirational)
- `ContextTextarea.tsx` — large textarea with char count, min 50 chars
- `SourceMaterialUpload.tsx` — textarea for pasting text + **file upload** (PDF/TXT/DOCX), shows filename and size after selection
- `SubmitButton.tsx` — submit with loading state, disabled until form valid
- Zod schema matching GenerateRequest
- Est: 4 hr

**T-038a: Implement AgentStatusBadge.tsx** ✨ NEW (Gap #7)
- Small badge/chip component showing which agent is currently active
- Props: `agentName: string`, `isActive: boolean`
- Displays: agent name + animated dot indicator (● pulsing when active)
- Agent name mapping: `insight_extractor` → "Insight Extractor", etc.
- Color-coded by agent (each of 5 agents gets a distinct color)
- Used within PipelineProgress component
- Est: 45 min

**T-039: Implement PipelineProgress component**
- 5-step horizontal progress bar
- Each step: icon, label, status indicator (pending/active/completed/failed)
- Integrates AgentStatusBadge to show active agent name
- Animated transitions between states (Framer Motion)
- Est: 2 hr

**T-040: Implement StageCard component**
- Shows current stage details: name, description, elapsed time
- Spinner animation while running
- Transitions to "awaiting approval" state
- Est: 1 hr

**T-041: Implement CheckpointModal component**
- Modal overlay (Framer Motion enter/exit)
- Header: stage name, step X of 5
- Body: renders stage-specific review component
- Footer: Approve button (green), Reject button (red), optional Edit toggle
- Handles approve/reject via useCheckpoint hook
- Est: 2 hr

**T-042: Implement stage-specific review components**
- `InsightReview.tsx` — renders InsightSet as themed cards (themes, key messages, audience notes)
- `OutlineReview.tsx` — renders DeckOutline as a tree/list (sections, narrative arc, archetype badge)
- `SlidesReview.tsx` — renders slide list as compact cards (title, key points count, section)
- `AppendixReview.tsx` — renders appendix slides similarly
- `ValidationReport.tsx` — renders violations as warning cards or "All checks passed" success
- Est: 4 hr (5 components, ~45 min each)

**T-043: Implement PipelineLog component**
- Scrolling log area showing pipeline events
- Events: "Stage started", "Stage completed", "Awaiting approval", "Approved", "Rejected"
- Auto-scroll to bottom on new events
- Timestamps in relative format
- Est: 1 hr

**T-044: Implement PipelinePage**
- Combines PipelineProgress, StageCard, CheckpointModal, PipelineLog
- Uses useDeckStatus hook for polling
- Shows CheckpointModal when status is AWAITING_APPROVAL
- Redirects to GalleryPage on COMPLETED
- Error state rendering on FAILED
- Est: 2 hr

**T-045: Implement SlideCard component**
- Card layout: section badge, title, key points (bulleted), evidence count, metaphor, takeaway
- Hover state with edit button
- Expand/collapse for full details (speaker notes, visual, assets)
- Est: 2 hr

**T-045a: Implement EvidenceEditor.tsx** ✨ NEW (Gap #5)
- Edit evidence items within a slide
- Add/remove/edit evidence objects (type dropdown + detail textarea)
- Enforces max 3 items — "Add" button disabled at 3, shows counter "2/3"
- Valid evidence types: metric, reference, quote, benchmark, case_study
- Used within SlideEditor
- Tests: add item, remove item, max 3 enforcement, type validation
- Est: 1.5 hr

**T-045b: Implement KeyPointsEditor.tsx** ✨ NEW (Gap #5)
- Manage key_points list within a slide
- Add/remove/reorder (drag or up/down arrows)
- Enforces max 5 items with inline counter "3/5"
- Each point: inline text input with delete button
- "Add" button disabled at 5
- Used within SlideEditor
- Tests: add point, remove point, reorder, max 5 enforcement
- Est: 1.5 hr

**T-045c: Implement MetaphorEditor.tsx** ✨ NEW (Gap #5)
- Edit metaphor field for a slide
- Single textarea input
- Inline validator: must be exactly 1 sentence
  - Shows error if multiple periods found (excluding common abbreviations like "e.g.", "i.e.", "vs.", "Dr.", "Mr.", "Mrs.")
  - Red border + error message: "Metaphor must be exactly one sentence"
  - Green check when valid
- Used within SlideEditor
- Tests: single sentence passes, multiple sentences fails, abbreviations don't trigger false positive
- Est: 1 hr

**T-045d: Implement VisualEditor.tsx** ✨ NEW (Gap #5)
- Edit visual layout type and illustration_prompt fields
- Layout type: dropdown with options from STEP 8 (title, two-column, chart, timeline, table, quote, full-bleed visual, framework diagram)
- Illustration prompt fields:
  - Type: dropdown from STEP 7 (process-diagram, architecture-diagram, data-chart, comparison-table, timeline, framework, matrix, before-after)
  - Description: textarea
  - Alt text: text input
- Used within SlideEditor
- Tests: layout selection, illustration type selection, field updates
- Est: 1.5 hr

**T-046: Implement SlideEditor component** (REVISED — now composes sub-editors)
- Inline edit form within SlideCard (toggle via edit button)
- Composes sub-editor components:
  - `KeyPointsEditor` for key_points
  - `EvidenceEditor` for evidence
  - `MetaphorEditor` for metaphor
  - `VisualEditor` for visual/illustration_prompt
- Additional editable fields: title (text input), takeaway (text input), speaker_notes (textarea)
- Read-only fields: slide_id, section
- Save/Cancel buttons, validation delegated to sub-editors
- Calls updateSlide API on save
- Est: 2 hr

**T-046a: Implement AppendixSection.tsx** ✨ NEW (Gap #6)
- Dedicated component for rendering appendix slides
- Collapsible section below main slides list
- Header: "Appendix" label + slide count badge (e.g., "Appendix (3 slides)")
- Expand/collapse toggle (chevron icon, Framer Motion animation)
- Collapsed by default
- When expanded: renders appendix slides using SlideCard components
- Slides use "A01", "A02" numbering
- Tests: renders collapsed, expand/collapse toggle, shows correct count, renders slides when expanded
- Est: 1.5 hr

**T-047: Implement SlideList component**
- Ordered list of SlideCards
- Section grouping with headers
- Slide count per section
- Renders AppendixSection at the bottom
- Est: 1 hr

**T-048: Implement DeckSummary component**
- Card showing: deck title, type badge, audience, tone, total slides, decision/inform/ask
- Edit button for title/audience (stretch goal)
- Est: 1 hr

**T-049: Implement GalleryPage** (REVISED — Export moved to Tab 3)
- Combines DeckSummary, SlideList (with AppendixSection)
- Fetches deck data on mount
- Handles slide edits via SlideEditor
- Toast on successful save
- **No longer includes ExportButton or VersionHistory** (moved to ExportPage)
- Est: 1.5 hr

**T-050a: Implement JsonPreview.tsx** ✨ NEW (Gap #2)
- Syntax-highlighted JSON display of the full deck JSON
- Uses `react-syntax-highlighter` with a dark theme (e.g., `oneDark`)
- Collapsible sections for large decks
- Copy-to-clipboard button
- Props: `deck: Deck`
- Est: 1.5 hr

**T-050b: Implement ExportPage.tsx (Tab 3)** ✨ NEW (Gap #2) — 🔴 CRITICAL
- Dedicated page for Tab 3: Export
- Composes:
  - `JsonPreview.tsx` — full deck JSON with syntax highlighting
  - `VersionHistory.tsx` — list of saved versions (reuse from original T-049)
  - `ExportButton.tsx` — trigger export and download (reuse from original T-048)
- Layout: JsonPreview takes main area, VersionHistory in sidebar, ExportButton prominent at top
- Fetches deck data on mount via API
- Est: 2 hr

**T-050c: Wire 3-tab navigation** ✨ NEW (Gap #2 cont.)
- Update AppShell/routing to support 3 tabs:
  - Tab 1: IntakePage → PipelinePage (during generation)
  - Tab 2: GalleryPage (enabled after COMPLETED)
  - Tab 3: ExportPage (enabled after deck exists)
- TabBar disabled states enforced based on session status
- URL routing: `/`, `/gallery/:sessionId`, `/export/:sessionId`
- Est: 1 hr

**T-051: Implement ExportButton component** (moved from Phase 6)
- Button that triggers export API call
- Downloads JSON file on success (blob URL)
- Loading state during export
- Est: 1 hr

**T-051a: Implement VersionHistory component** (moved from Phase 6)
- Lists deck versions (fetched from history API)
- Each version: timestamp, version number, action (view/download)
- Est: 1 hr

---

## Phase 7: Tests (T-052 → T-061)

**T-052: Backend test infrastructure**
- `pytest.ini` — asyncio_mode=auto, test paths, markers (unit, integration, e2e)
- `tests/conftest.py` — FastAPI TestClient fixture (httpx.AsyncClient), mock orchestrator fixture, sample data fixtures, temp directory for exports
- `tests/factories.py` — factory_boy factories: SlideFactory, DeckFactory, DeckEnvelopeFactory, GenerateRequestFactory
- Est: 2 hr

**T-053: Backend unit tests — schemas**
- `test_schemas_input.py` — valid/invalid GenerateRequest, field constraints, type literals
- `test_schemas_output.py` — Slide constraints (key_points max 5, evidence max 3, metaphor sentence), Deck validation, DeckEnvelope round-trip
- `test_settings.py` — settings load from env, defaults, missing required vars
- Est: 2 hr

**T-054: Backend unit tests — agents**
- `test_insight_extractor.py` — subagent config structure, prompt contains required instructions, tool is callable
- `test_deck_architect.py` — same pattern
- `test_slide_generator.py` — same pattern
- `test_appendix_agent.py` — same pattern
- `test_quality_validator.py` — **detailed tests**: run validate_deck against valid deck (pass), deck with 6 key_points (fail), deck with 4 evidence items (fail), multi-sentence metaphor (fail)
- `test_orchestrator.py` — orchestrator graph is created, has correct number of subagents, interrupt_on is set
- `test_prompt_integration.py` — **all 5 agents' system prompts start with PRESENTATION_ARCHITECT_PROMPT** (from T-017a)
- Est: 3.5 hr

**T-054a: Backend unit tests — source material service** ✨ NEW
- `test_source_material_service.py`:
  - Extract text from PDF (fixture file)
  - Extract text from TXT (fixture file with utf-8 and latin-1)
  - Extract text from DOCX (fixture file)
  - Reject unsupported MIME type (e.g., image/png)
  - Reject oversized file
  - Handle empty/corrupt PDF gracefully
- Create fixture files in `tests/fixtures/`
- Est: 1.5 hr

**T-055: Backend unit tests — services**
- `test_session_service.py` — create, get, update status, add checkpoint, resolve checkpoint, state transitions
- `test_file_service.py` — export writes file, version incrementing, list versions, read version
- Est: 2 hr

**T-055a: Backend unit tests — session restore** ✨ NEW
- `test_session_restore.py`:
  - Write mock session files to temp SESSION_DIR
  - Include COMPLETED, FAILED, RUNNING, AWAITING_APPROVAL sessions
  - Run restore logic
  - Assert only non-terminal sessions with valid checkpoints are restored
  - Assert terminal sessions are skipped
  - Assert sessions without checkpoints are marked FAILED
- Est: 1.5 hr

**T-056: Backend integration tests**
- `test_pipeline_flow.py` — mock LLM responses, run full pipeline, verify 5 interrupts occur in order, verify final deck structure
- `test_checkpoint_approve.py` — approve a checkpoint, verify pipeline resumes, next stage starts
- `test_checkpoint_reject.py` — reject a checkpoint, verify pipeline halts, session status = REJECTED
- `test_quality_loop.py` — mock validator to return violations, verify slide_generator is called again, max 3 retries
- `test_session_persistence.py` — create session, checkpoint, "restart" (clear in-memory), verify can resume from SQLite
- Est: 4 hr

**T-057: Backend E2E tests**
- `test_generate_deck.py` — HTTP: POST /generate → poll status → approve 5 checkpoints → GET deck → verify structure
- `test_edit_slide.py` — HTTP: complete pipeline → PUT slide → verify update persisted
- `test_export.py` — HTTP: complete pipeline → POST export → verify JSON file content
- `test_file_upload.py` — HTTP: POST /generate with PDF file attachment → verify source_material extracted
- All use httpx.AsyncClient against real FastAPI app with mocked LLM
- Est: 3.5 hr

**T-058: Frontend test infrastructure**
- `vitest.config.ts` — jsdom environment, setup file, coverage config
- `playwright.config.ts` — base URL, projects (chromium), web server command
- `tests/setup.ts` — testing-library matchers, MSW server setup
- `tests/mocks/` — handlers.ts (MSW request handlers), server.ts (MSW server), data.ts (mock deck/session data), api.ts (mock API responses), store.ts (mock Zustand store)
- Est: 2 hr

**T-059: Frontend unit tests**
- `deckStore.test.ts` — store actions, state mutations, polling logic
- `deckApi.test.ts` — API functions call correct endpoints with correct params
- `validation.test.ts` — Zod schemas validate/reject correctly
- `hooks.test.ts` — hook behavior with mocked store (including useDeckStatus)
- `useDeckStatus.test.ts` — polling starts/stops, terminal state handling, activeAgent extraction
- Est: 2.5 hr

**T-060: Frontend component tests (24 files)** (REVISED — more components now)
- One test file per component: render, user interaction, state changes
- Priority components:
  - `CheckpointModal` — approve/reject flow
  - `SlideEditor` — form validation, sub-editor composition
  - `EvidenceEditor` — add/remove, max 3
  - `KeyPointsEditor` — add/remove/reorder, max 5
  - `MetaphorEditor` — sentence validation
  - `VisualEditor` — dropdown selections
  - `TabBar` — disabled states, tab switching
  - `AppendixSection` — expand/collapse
  - `AgentStatusBadge` — active/inactive states
  - `JsonPreview` — renders JSON, copy button
  - `ExportPage` — composition of sub-components
  - `DeckTypeSelector` — selection
  - `PipelineProgress` — status rendering
- Use @testing-library/react, mock API calls via MSW
- Est: 8 hr (24 components × ~20 min each)

**T-061: Frontend E2E tests (Playwright)**
- `full-flow.spec.ts` — Fill form → submit → approve all checkpoints → view gallery → switch to export tab → export
- `hitl-checkpoints.spec.ts` — Approve some, reject one, verify pipeline behavior
- `slide-editing.spec.ts` — Navigate to gallery, edit a slide (use sub-editors), save, verify
- `tab-navigation.spec.ts` — Verify tab disabled states, tab switching, URL changes
- `file-upload.spec.ts` — Upload PDF via intake form, verify processing
- Run against dev server with MSW intercepting API calls
- Est: 4 hr

---

## Phase 8: Deployment (T-062 → T-063)

**T-062: Server setup and SSL**
- Create deckstudio user on server
- Create directory structure on server
- Install Python 3.11 if not present
- Install Node.js 20+ if not present (for frontend build)
- Copy nginx config, enable site
- Run certbot for SSL
- Copy systemd service, enable
- Est: 2 hr

**T-063: First deployment and smoke test**
- Copy backend files to `/opt/deckstudio/backend/`
- Create `.env` with real API keys
- Install Python deps in venv
- Build frontend locally, copy dist to `/var/www/deckstudio/`
- Start systemd service
- Verify: `curl https://deckstudio.karlekar.cloud/api/health`
- Verify: frontend loads in browser
- Smoke test: create a deck, approve all checkpoints, export
- Verify: Presentation Architect Prompt is loaded (check logs for first 100 chars)
- Est: 2 hr

---

## Summary

| Phase | Tasks | Est. Hours |
|---|---|---|
| 1. Project Setup & Infrastructure | T-001 → T-007 + T-001a, T-002a, T-006a | 7.5 |
| 2. Backend — Core Schemas & Config | T-008 → T-011a | 5 |
| 3. Backend — DeepAgents Pipeline | T-012 → T-021 + T-017a | 20.5 |
| 4. Backend — FastAPI Routes & Services | T-022 → T-030 + T-022a, T-029a | 17 |
| 5. Frontend — Foundation | T-031 → T-037 + T-033a, T-034a, T-034b | 12.5 |
| 6. Frontend — Components | T-038 → T-051a + new components | 33 |
| 7. Tests | T-052 → T-061 + T-054a, T-055a | 36.5 |
| 8. Deployment | T-062 → T-063 | 4 |
| **Total** | **79 tasks** | **~136 hrs** |

### New Tasks Summary (17 additions)

| Task | Description | Gap # | Priority |
|------|-------------|-------|----------|
| T-001a | Root .gitignore | 12 | 🟢 |
| T-002a | Python __init__.py files | 11 | 🟢 |
| T-006a | Frontend .env/.env.example | 10 | 🟢 |
| T-008 | Save Presentation Architect Prompt | 1 | 🔴 |
| T-017a | Verify prompt integration (tests) | 1 | 🔴 |
| T-022a | SourceMaterialService | 3 | 🔴 |
| T-029a | Session restore on startup | 8 | 🟡 |
| T-033a | useDeckStatus.ts hook | 9 | 🟡 |
| T-034a | TabBar.tsx | 4 | 🟡 |
| T-034b | AppShell.tsx | 13 | 🟢 |
| T-038a | AgentStatusBadge.tsx | 7 | 🟡 |
| T-045a | EvidenceEditor.tsx | 5 | 🟡 |
| T-045b | KeyPointsEditor.tsx | 5 | 🟡 |
| T-045c | MetaphorEditor.tsx | 5 | 🟡 |
| T-045d | VisualEditor.tsx | 5 | 🟡 |
| T-046a | AppendixSection.tsx | 6 | 🟡 |
| T-050a-c | ExportPage + JsonPreview + wiring | 2 | 🔴 |

### Dependency Chain (Updated)

```
Phase 1 (Setup + .gitignore + __init__.py + .env files)
  └→ Phase 2 (Schemas + Presentation Architect Prompt)
       └→ Phase 3 (DeepAgents Pipeline + Prompt Integration + Prompt Loader)
       └→ Phase 5 (Frontend Foundation — types + hooks + TabBar + AppShell)
            └→ Phase 6 (Frontend Components + Sub-editors + ExportPage + AppendixSection)
  Phase 3 + Phase 2
       └→ Phase 4 (Routes + SourceMaterialService + Session Restore)
  Phase 4 + Phase 6
       └→ Phase 7 (Tests — needs both backend + frontend)
  Phase 7
       └→ Phase 8 (Deployment — after tests pass)
```

### Critical Path

The **Presentation Architect Prompt** (T-008) is now the first content task after project setup. It blocks all 5 agent implementations. This is intentional — the prompt is the soul of the project and must exist before any agent code is written.
