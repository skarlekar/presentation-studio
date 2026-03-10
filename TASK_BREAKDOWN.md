# Presentation Studio — Task Breakdown

> **Project:** DeckStudio  
> **Date:** 2026-03-10  
> **Total Tasks:** 62  
> **Estimated Total Effort:** ~120-180 hours  
> **Reference:** IMPLEMENTATION_PLAN_V2.md

---

## Phase 1: Project Setup & Infrastructure (T-001 → T-007)

**T-001: Create project directory structure**
- Create `/opt/deckstudio/{backend,data/{sessions,exports},logs}`, `/var/www/deckstudio/`
- Create system user `deckstudio`
- Set permissions
- Est: 30 min

**T-002: Initialize backend Python project**
- Create `backend/` directory structure: `config/`, `schemas/`, `agents/`, `services/`, `api/routes/`, `tests/`
- Create `requirements.txt` with all dependencies: `fastapi`, `uvicorn`, `deepagents`, `langgraph`, `langchain-anthropic`, `pydantic[dotenv]`, `pydantic-settings`, `python-dotenv`, `aiofiles`
- Create `requirements-test.txt`: `pytest`, `pytest-asyncio`, `httpx`, `factory-boy`, `respx`
- Create Python venv, install deps
- Verify `from deepagents import create_deep_agent` works
- Est: 1 hr

**T-003: Initialize frontend React/TypeScript project**
- `npm create vite@latest frontend -- --template react-ts`
- Install deps: `tailwindcss`, `postcss`, `autoprefixer`, `react-router-dom`, `axios`, `react-hook-form`, `@hookform/resolvers`, `zod`, `zustand`, `lucide-react`, `react-hot-toast`, `framer-motion`
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

**T-007: Create README.md**
- Project overview, setup instructions (dev + prod), architecture summary, API docs link
- Est: 1 hr

---

## Phase 2: Backend — Core Schemas & Config (T-008 → T-011)

**T-008: Implement input schemas (schemas/input.py)**
- `GenerateRequest` — title, type (Literal 5 types), audience, tone, decision_inform_ask, context, source_material (optional), total_slides (optional)
- Field validators: type must be one of 5 Literal values, context min 50 chars, audience non-empty
- Est: 1 hr

**T-009: Implement output schemas (schemas/output.py)**
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

**T-010: Implement Insights and Outline intermediate schemas**
- `InsightSet(BaseModel)` — themes: List[str], key_messages: List[str], audience_considerations: List[str], constraints: List[str]
- `DeckOutline(BaseModel)` — archetype, narrative_arc, sections: List[SectionOutline], estimated_slides
- These are structured outputs for stages 1 and 2, used as checkpoint previews
- Est: 1 hr

**T-011: Implement ValidationReport schema**
- `Violation(BaseModel)` — slide_id, field, constraint, actual_value, message
- `ValidationReport(BaseModel)` — valid: bool, violations: List[Violation], checked_at: datetime
- Est: 30 min

---

## Phase 3: Backend — DeepAgents Pipeline (T-012 → T-020)

**T-012: Implement InsightExtractorAgent (agents/insight_extractor.py)**
- Define system prompt: specialized for extracting insights from unstructured context
- Define `extract_insights` tool using `@tool` decorator
- Export subagent config dict: `{"name": "insight_extractor", "description": ..., "system_prompt": ..., "tools": [...], "model": ...}`
- Set `response_format=InsightSet`
- Est: 2 hr

**T-013: Implement DeckArchitectAgent (agents/deck_architect.py)**
- Define system prompt: specialized for deck structure design, narrative arcs, section planning
- Define `design_outline` tool
- Export subagent config dict
- Set `response_format=DeckOutline`
- Include deck archetype selection logic in prompt (Decision/Strategy/Update/TechDeep/Pitch patterns)
- Est: 2 hr

**T-014: Implement SlideGeneratorAgent (agents/slide_generator.py)**
- Define system prompt: generates slide content matching Slide schema exactly
- Define `generate_slides` tool
- Export subagent config dict
- Set `response_format` for list of Slides
- Prompt must emphasize: title = conclusion statement, metaphor = 1 sentence, key_points ≤ 5, evidence ≤ 3
- Est: 2 hr

**T-015: Implement AppendixAgent (agents/appendix_agent.py)**
- Define system prompt: generates supporting appendix content
- Define `build_appendix` tool
- Export subagent config dict
- Set `response_format=Appendix`
- Est: 1.5 hr

**T-016: Implement QualityValidatorAgent (agents/quality_validator.py)**
- Define system prompt: validates schema compliance
- Define `validate_deck` tool — this one has **real logic** (not just LLM):
  - Check key_points length ≤ 5 per slide
  - Check evidence length ≤ 3 per slide
  - Check metaphor is single sentence (count periods, exclude abbreviations)
  - Check title is a conclusion statement (heuristic)
  - Return ValidationReport
- Can be hybrid: LLM for semantic checks (is title really a conclusion?), pure Python for structural checks
- Est: 2 hr

**T-017: Implement Orchestrator (agents/orchestrator.py)**
- Import all 5 subagent configs
- Initialize `SqliteSaver` checkpointer from settings
- Call `create_deep_agent()` with orchestrator system prompt, subagents list, `interrupt_on={"task": True}`
- Export the compiled graph
- Handle model override from settings
- Est: 2 hr

**T-018: Implement pipeline runner function**
- Async function `run_pipeline(session_id, request, session_service)`
- Format GenerateRequest into initial message for orchestrator
- Call `orchestrator.invoke()` with thread_id config
- After each return (interrupt or completion), update session via session_service
- Detect interrupt state: check `graph.get_state(config).next` — if non-empty, pipeline is paused
- Extract pending tool call info for checkpoint data
- Handle exceptions, update session to FAILED on error
- Est: 3 hr

**T-019: Implement checkpoint resume logic**
- Function `resume_pipeline(session_id, edits=None)`
- If edits provided: use `Command(resume=edited_data)` to modify the pending tool call
- If no edits: `orchestrator.invoke(None, config)` to resume as-is
- After resume, check if next interrupt or completion
- Update session state accordingly
- Est: 2 hr

**T-020: Implement quality validation retry loop handling**
- In orchestrator system prompt: instruct max 3 retries when validator fails
- Each retry triggers another `task("slide_generator", ...)` call → another interrupt
- Track retry count in session service
- On 4th failure: force completion with warnings attached to deck
- Est: 1.5 hr

---

## Phase 4: Backend — FastAPI Routes & Session Management (T-021 → T-029)

**T-021: Implement SessionService (services/session_service.py)**
- In-memory dict[str, Session] for active sessions
- Methods: `create_session()`, `get_session()`, `update_status()`, `add_checkpoint()`, `resolve_checkpoint()`, `set_deck()`, `get_all_sessions()`
- Session dataclass with all fields from Plan §5
- Thread-safe with asyncio Lock
- Est: 2 hr

**T-022: Implement FileService (services/file_service.py)**
- `export_deck(session_id, deck)` → write versioned JSON to export dir
- `get_deck_versions(session_id)` → list versions
- `get_deck_version(session_id, version)` → read specific version
- Filename pattern: `{session_id}_v{version}_{timestamp}.json`
- Use `aiofiles` for async I/O
- Est: 1.5 hr

**T-023: Implement POST /api/deck/generate route**
- Validate `GenerateRequest` body
- Create session via session_service
- Spawn `asyncio.create_task(run_pipeline(...))`
- Return `{session_id, status: "PENDING"}`
- Est: 1 hr

**T-024: Implement GET /api/deck/{session_id}/status route**
- Return current session status, current_stage, checkpoints list
- If AWAITING_APPROVAL: include current checkpoint details with pending_input and preview
- Est: 1 hr

**T-025: Implement POST /api/deck/{session_id}/checkpoint/{checkpoint_id}/approve route**
- Accept optional `edits` body
- Resolve checkpoint as approved in session_service
- Call `resume_pipeline(session_id, edits)`
- Spawn background task for next pipeline segment
- Return updated status
- Est: 1.5 hr

**T-026: Implement POST /api/deck/{session_id}/checkpoint/{checkpoint_id}/reject route**
- Accept `reason` in body
- Resolve checkpoint as rejected
- For MVP: halt pipeline, set session to REJECTED
- Return updated status
- Est: 1 hr

**T-027: Implement deck CRUD routes**
- `GET /api/deck/{session_id}` — return full deck if completed
- `PUT /api/deck/{session_id}/slide/{slide_id}` — update single slide, increment version
- `POST /api/deck/{session_id}/approve` — mark deck as finally approved (post-editing)
- Est: 1.5 hr

**T-028: Implement export and history routes**
- `POST /api/deck/{session_id}/export` — trigger file_service.export_deck(), return download URL
- `GET /api/deck/{session_id}/history` — return version list from file_service
- Est: 1 hr

**T-029: Implement health route and FastAPI app setup (main.py, api/routes/health.py)**
- `GET /api/health` — return `{status: "ok", version: "1.0.0"}`
- `main.py`: FastAPI app with CORS middleware, include routers, startup/shutdown events
- Startup: initialize session_service, verify checkpoint DB accessible
- CORS: allow configured origins
- Est: 1.5 hr

---

## Phase 5: Frontend — Foundation (T-030 → T-036)

**T-030: Implement TypeScript types (src/types/deck.ts, src/types/api.ts)**
- Mirror all backend Pydantic schemas as TypeScript interfaces
- `deck.ts`: Slide, Deck, DeckEnvelope, EvidenceItem, Visual, Appendix, InsightSet, DeckOutline, ValidationReport
- `api.ts`: GenerateRequest, GenerateResponse, SessionStatus, Checkpoint, PipelineStatus enum
- Est: 1.5 hr

**T-031: Implement API client (src/api/deckApi.ts)**
- Axios instance with base URL config (env-dependent)
- Functions: `generateDeck()`, `getStatus()`, `approveCheckpoint()`, `rejectCheckpoint()`, `getDeck()`, `updateSlide()`, `approveDeck()`, `exportDeck()`, `getHistory()`
- Error handling wrapper with toast notifications
- Est: 1.5 hr

**T-032: Implement Zustand store (src/store/deckStore.ts)**
- Full store interface as defined in Plan §6
- Actions that call deckApi functions
- Polling integration (set interval in store action)
- Est: 2 hr

**T-033: Implement custom hooks**
- `usePipelinePolling.ts` — manages polling interval, auto-stop on terminal states
- `useCheckpoint.ts` — provides approve/reject handlers with optimistic updates
- `useDeckExport.ts` — handles export trigger and download
- Est: 1.5 hr

**T-034: Implement Layout components**
- `Header.tsx` — logo ("DeckStudio"), navigation (New Deck / Active Session)
- `Footer.tsx` — minimal footer
- `Layout.tsx` — wraps pages with Header/Footer, Toaster provider
- Est: 1 hr

**T-035: Implement App.tsx and routing**
- React Router v6 setup: `/`, `/pipeline/:sessionId`, `/gallery/:sessionId`
- Wrap with Layout
- Est: 30 min

**T-036: Implement main.tsx and index.html**
- `main.tsx` — React root render with BrowserRouter
- `index.html` — HTML shell with Tailwind CSS, meta tags, favicon
- Est: 30 min

---

## Phase 6: Frontend — Components (T-037 → T-050)

**T-037: Implement IntakePage with form components**
- `IntakePage.tsx` — page container, React Hook Form + Zod validation, submit handler
- `DeckTypeSelector.tsx` — 5 deck type cards (Decision, Strategy, Update, Tech Deep Dive, Pitch) with icons, selectable
- `AudienceInput.tsx` — text input with label
- `ToneSelector.tsx` — dropdown or chip selector (Professional, Conversational, Technical, Executive, Inspirational)
- `ContextTextarea.tsx` — large textarea with char count, min 50 chars
- `SourceMaterialUpload.tsx` — textarea for pasting text, optional file upload placeholder
- `SubmitButton.tsx` — submit with loading state, disabled until form valid
- Zod schema matching GenerateRequest
- Est: 4 hr

**T-038: Implement PipelineProgress component**
- 5-step horizontal progress bar
- Each step: icon, label, status indicator (pending/active/completed/failed)
- Animated transitions between states (Framer Motion)
- Est: 2 hr

**T-039: Implement StageCard component**
- Shows current stage details: name, description, elapsed time
- Spinner animation while running
- Transitions to "awaiting approval" state
- Est: 1 hr

**T-040: Implement CheckpointModal component**
- Modal overlay (Framer Motion enter/exit)
- Header: stage name, step X of 5
- Body: renders stage-specific review component
- Footer: Approve button (green), Reject button (red), optional Edit toggle
- Handles approve/reject via useCheckpoint hook
- Est: 2 hr

**T-041: Implement stage-specific review components**
- `InsightReview.tsx` — renders InsightSet as themed cards (themes, key messages, audience notes)
- `OutlineReview.tsx` — renders DeckOutline as a tree/list (sections, narrative arc, archetype badge)
- `SlidesReview.tsx` — renders slide list as compact cards (title, key points count, section)
- `AppendixReview.tsx` — renders appendix slides similarly
- `ValidationReport.tsx` — renders violations as warning cards or "All checks passed" success
- Est: 4 hr (5 components, ~45 min each)

**T-042: Implement PipelineLog component**
- Scrolling log area showing pipeline events
- Events: "Stage started", "Stage completed", "Awaiting approval", "Approved", "Rejected"
- Auto-scroll to bottom on new events
- Timestamps in relative format
- Est: 1 hr

**T-043: Implement PipelinePage**
- Combines PipelineProgress, StageCard, CheckpointModal, PipelineLog
- Starts polling on mount
- Shows CheckpointModal when status is AWAITING_APPROVAL
- Redirects to GalleryPage on COMPLETED
- Error state rendering on FAILED
- Est: 2 hr

**T-044: Implement SlideCard component**
- Card layout: section badge, title, key points (bulleted), evidence count, metaphor, takeaway
- Hover state with edit button
- Expand/collapse for full details (speaker notes, visual, assets)
- Est: 2 hr

**T-045: Implement SlideEditor component**
- Inline edit form within SlideCard (toggle via edit button)
- Editable fields: title, key_points (add/remove), metaphor, takeaway, speaker_notes
- Read-only fields: slide_id, section
- Save/Cancel buttons, validation (key_points ≤ 5, etc.)
- Calls updateSlide API on save
- Est: 2.5 hr

**T-046: Implement SlideList component**
- Ordered list of SlideCards
- Section grouping with headers
- Slide count per section
- Est: 1 hr

**T-047: Implement DeckSummary component**
- Card showing: deck title, type badge, audience, tone, total slides, decision/inform/ask
- Edit button for title/audience (stretch goal)
- Est: 1 hr

**T-048: Implement ExportButton component**
- Button that triggers export API call
- Downloads JSON file on success (blob URL)
- Loading state during export
- Est: 1 hr

**T-049: Implement VersionHistory component**
- Lists deck versions (fetched from history API)
- Each version: timestamp, version number, action (view/download)
- Est: 1 hr

**T-050: Implement GalleryPage**
- Combines DeckSummary, SlideList, ExportButton, VersionHistory
- Fetches deck data on mount
- Handles slide edits via SlideEditor
- Toast on successful save/export
- Est: 2 hr

---

## Phase 7: Tests (T-051 → T-060)

**T-051: Backend test infrastructure**
- `pytest.ini` — asyncio_mode=auto, test paths, markers (unit, integration, e2e)
- `tests/conftest.py` — FastAPI TestClient fixture (httpx.AsyncClient), mock orchestrator fixture, sample data fixtures, temp directory for exports
- `tests/factories.py` — factory_boy factories: SlideFactory, DeckFactory, DeckEnvelopeFactory, GenerateRequestFactory
- Est: 2 hr

**T-052: Backend unit tests — schemas**
- `test_schemas_input.py` — valid/invalid GenerateRequest, field constraints, type literals
- `test_schemas_output.py` — Slide constraints (key_points max 5, evidence max 3, metaphor sentence), Deck validation, DeckEnvelope round-trip
- `test_settings.py` — settings load from env, defaults, missing required vars
- Est: 2 hr

**T-053: Backend unit tests — agents**
- `test_insight_extractor.py` — subagent config structure, prompt contains required instructions, tool is callable
- `test_deck_architect.py` — same pattern
- `test_slide_generator.py` — same pattern
- `test_appendix_agent.py` — same pattern
- `test_quality_validator.py` — **detailed tests**: run validate_deck against valid deck (pass), deck with 6 key_points (fail), deck with 4 evidence items (fail), multi-sentence metaphor (fail)
- `test_orchestrator.py` — orchestrator graph is created, has correct number of subagents, interrupt_on is set
- Est: 3 hr

**T-054: Backend unit tests — services**
- `test_session_service.py` — create, get, update status, add checkpoint, resolve checkpoint, state transitions
- `test_file_service.py` — export writes file, version incrementing, list versions, read version
- Est: 2 hr

**T-055: Backend integration tests**
- `test_pipeline_flow.py` — mock LLM responses, run full pipeline, verify 5 interrupts occur in order, verify final deck structure
- `test_checkpoint_approve.py` — approve a checkpoint, verify pipeline resumes, next stage starts
- `test_checkpoint_reject.py` — reject a checkpoint, verify pipeline halts, session status = REJECTED
- `test_quality_loop.py` — mock validator to return violations, verify slide_generator is called again, max 3 retries
- `test_session_persistence.py` — create session, checkpoint, "restart" (clear in-memory), verify can resume from SQLite
- Est: 4 hr

**T-056: Backend E2E tests**
- `test_generate_deck.py` — HTTP: POST /generate → poll status → approve 5 checkpoints → GET deck → verify structure
- `test_edit_slide.py` — HTTP: complete pipeline → PUT slide → verify update persisted
- `test_export.py` — HTTP: complete pipeline → POST export → verify JSON file content
- All use httpx.AsyncClient against real FastAPI app with mocked LLM
- Est: 3 hr

**T-057: Frontend test infrastructure**
- `vitest.config.ts` — jsdom environment, setup file, coverage config
- `playwright.config.ts` — base URL, projects (chromium), web server command
- `tests/setup.ts` — testing-library matchers, MSW server setup
- `tests/mocks/` — handlers.ts (MSW request handlers), server.ts (MSW server), data.ts (mock deck/session data), api.ts (mock API responses), store.ts (mock Zustand store)
- Est: 2 hr

**T-058: Frontend unit tests**
- `deckStore.test.ts` — store actions, state mutations, polling logic
- `deckApi.test.ts` — API functions call correct endpoints with correct params
- `validation.test.ts` — Zod schemas validate/reject correctly
- `hooks.test.ts` — hook behavior with mocked store
- Est: 2 hr

**T-059: Frontend component tests (18 files)**
- One test file per component: render, user interaction, state changes
- Priority components: CheckpointModal (approve/reject flow), SlideEditor (form validation), DeckTypeSelector (selection), PipelineProgress (status rendering)
- Use @testing-library/react, mock API calls via MSW
- Est: 6 hr (18 components × ~20 min each)

**T-060: Frontend E2E tests (Playwright)**
- `full-flow.spec.ts` — Fill form → submit → approve all checkpoints → view gallery → export
- `hitl-checkpoints.spec.ts` — Approve some, reject one, verify pipeline behavior
- `slide-editing.spec.ts` — Navigate to gallery, edit a slide, save, verify
- Run against dev server with MSW intercepting API calls
- Est: 3 hr

---

## Phase 8: Deployment (T-061 → T-062)

**T-061: Server setup and SSL**
- Create deckstudio user on server
- Create directory structure on server
- Install Python 3.11 if not present
- Install Node.js 20+ if not present (for frontend build)
- Copy nginx config, enable site
- Run certbot for SSL
- Copy systemd service, enable
- Est: 2 hr

**T-062: First deployment and smoke test**
- Copy backend files to `/opt/deckstudio/backend/`
- Create `.env` with real API keys
- Install Python deps in venv
- Build frontend locally, copy dist to `/var/www/deckstudio/`
- Start systemd service
- Verify: `curl https://deckstudio.karlekar.cloud/api/health`
- Verify: frontend loads in browser
- Smoke test: create a deck, approve all checkpoints, export
- Est: 2 hr

---

## Summary

| Phase | Tasks | Est. Hours |
|---|---|---|
| 1. Project Setup & Infrastructure | T-001 → T-007 | 6 |
| 2. Backend — Core Schemas & Config | T-008 → T-011 | 4.5 |
| 3. Backend — DeepAgents Pipeline | T-012 → T-020 | 18 |
| 4. Backend — FastAPI Routes & Services | T-021 → T-029 | 13 |
| 5. Frontend — Foundation | T-030 → T-036 | 8.5 |
| 6. Frontend — Components | T-037 → T-050 | 24.5 |
| 7. Tests | T-051 → T-060 | 29 |
| 8. Deployment | T-061 → T-062 | 4 |
| **Total** | **62 tasks** | **~107.5 hrs** |

### Dependency Chain

```
Phase 1 (Setup)
  └→ Phase 2 (Schemas) 
       └→ Phase 3 (DeepAgents Pipeline)
       └→ Phase 5 (Frontend Foundation — types mirror schemas)
            └→ Phase 6 (Frontend Components)
  Phase 3 + Phase 2 
       └→ Phase 4 (Routes — needs pipeline + schemas)
  Phase 4 + Phase 6
       └→ Phase 7 (Tests — needs both backend + frontend)
  Phase 7
       └→ Phase 8 (Deployment — after tests pass)
```

### Parallelization Opportunities

- **Phase 3 + Phase 5** can run in parallel (backend agents + frontend foundation)
- **Phase 4 + Phase 6** can partially overlap (routes don't block component work if types are done)
- **T-051/T-057** (test infrastructure) can start as soon as Phase 2 completes
- Individual agent files (T-012 through T-016) are independent of each other
