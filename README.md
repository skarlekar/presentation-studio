# 🎯 Presentation Studio

> AI-powered executive presentation deck generator with human-in-the-loop review at every stage.

**Live at:** https://deckstudio.karlekar.cloud

---

## What It Does

Presentation Studio transforms unstructured context and requirements into McKinsey/BCG-caliber slide decks using a 5-agent AI pipeline. At every critical stage, a human reviews and approves before the pipeline continues.

### The 3-Tab Workflow

| Tab | Purpose |
|-----|---------|
| **1. Intake** | Fill in context, audience, tone, slide count, optional source material |
| **2. Gallery** | Watch the 5-agent pipeline run, approve/edit at each checkpoint, then edit slide cards inline |
| **3. Export** | Preview JSON, view version history, download |

### The 5-Agent Pipeline

```
InsightExtractor  →  [HITL: Confirm insights]
DeckArchitect     →  [HITL: Confirm outline]
SlideGenerator    →  [HITL: Review slides]
AppendixBuilder   →  [HITL: Confirm appendix]
QualityValidator  →  PASS → done | FAIL → retry (max 3x)
```

Every agent uses the **Presentation Architect Prompt** — a detailed system prompt enforcing McKinsey/BCG-style output: conclusion-statement titles, mandatory metaphors, evidence-backed claims, consulting visual language.

---

## Tech Stack

### Backend
- **Python 3.11+** · FastAPI · uvicorn
- **DeepAgents** (langchain-ai/deepagents) — agent harness with HITL
- **LangGraph** — stateful pipeline with `SqliteSaver` checkpointing
- **Pydantic v2** — strict schema validation

### Frontend
- **React 18+** · TypeScript · Vite
- **Tailwind CSS** · Framer Motion · Lucide React
- **Zustand** — global state · **React Hook Form + Zod** — form validation

---

## Project Structure

```
presentation-studio/
├── backend/                    # FastAPI + DeepAgents pipeline
│   ├── prompts/
│   │   └── presentation_architect.txt   # ← The soul of the project
│   ├── agents/                 # 5 DeepAgents subagent definitions
│   ├── schemas/                # Pydantic v2 input/output schemas
│   ├── services/               # Session, file, source material services
│   ├── api/routes/             # FastAPI routes
│   └── tests/                  # pytest suite (≥85% coverage)
├── frontend/                   # React/TypeScript SPA
│   ├── src/
│   │   ├── pages/              # IntakePage, GalleryPage, ExportPage
│   │   ├── components/         # intake/, pipeline/, gallery/, export/
│   │   ├── store/              # Zustand store
│   │   └── hooks/              # Pipeline polling, checkpoint, export hooks
│   └── tests/                  # Vitest + Playwright (≥80% coverage)
├── deploy/                     # nginx config, systemd service, deploy script
└── docs/                       # Implementation plan, task breakdown, prompt architecture
```

---

## Quick Start

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npx vitest
cd frontend && npx playwright test
```

---

## The Presentation Architect Prompt

The file `backend/prompts/presentation_architect.txt` is the **soul of this project**. It is a comprehensive system prompt embedded verbatim in every agent LLM call, instructing the model to behave as an elite strategy consultant.

Key requirements it enforces on every slide:
- **Title** = conclusion statement (not a topic label)
- **Metaphor** = exactly 1 sentence, layman-accessible analogy
- **key_points** ≤ 5 items
- **evidence** ≤ 3 items, ranked by type priority
- **Visual** with specific layout + illustration prompt

> ⚠️ Never modify `presentation_architect.txt` without design review. It is the single source of truth for output quality.

---

## Deployment

Deployed on a Linux server with:
- **nginx** as reverse proxy (serves React SPA + proxies `/api/` to port 8001)
- **systemd** service for the FastAPI backend
- **certbot** for SSL

See `deploy/` for nginx config and systemd unit files.

---

## Documentation

| File | Contents |
|------|----------|
| `docs/IMPLEMENTATION_PLAN_V2.md` | Full architecture, DeepAgents design, HITL flow |
| `docs/TASK_BREAKDOWN_V2.md` | 79 ordered implementation tasks |
| `docs/PROMPT_ARCHITECTURE.md` | How the Presentation Architect Prompt is loaded and composed |

---

*Built with ⚡ by [Spark/OpenClaw](https://github.com/skarlekar)*
