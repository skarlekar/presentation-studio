# Prompt Architecture — DeckStudio

> **Date:** 2026-03-10  
> **Status:** Canonical reference document  
> **Audience:** Anyone implementing or reviewing agent code

---

## 1. Overview

The **Presentation Architect Prompt** is the soul of DeckStudio. It is a multi-page system prompt that instructs the LLM to behave as an elite strategy consultant, producing McKinsey/BCG-caliber slide decks with evidence-driven content, narrative coherence, and mandatory metaphors on every slide.

**Every single LLM call** in DeckStudio's 5-agent pipeline must include this prompt as the foundation of its system prompt. No agent should ever call the LLM without it.

---

## 2. The Canonical File

**Location:** `backend/prompts/presentation_architect.txt`

This file contains the full Presentation Architect Prompt verbatim — approximately 6,000 words covering:

- **ROLE** — Elite strategy consultant identity
- **INPUT PLACEHOLDERS** — Required and optional inputs with validation rules
- **HARD RULES** — Stop-if-missing-inputs, mandatory metaphors
- **STEP 1** — Extract Insights From Documents
- **STEP 2** — Determine Deck Archetype
- **STEP 3** — Narrative Story Arc
- **STEP 4** — Executive Summary Compression
- **STEP 5** — Slide Contract (Mandatory)
- **STEP 6** — Visual Design System
- **STEP 7** — Visual Generation Prompts
- **STEP 8** — Slide Layout Types
- **STEP 9** — Output Format (Required) — full JSON schema
- **STEP 10** — Appendix Auto-Generation
- **STEP 11** — Evidence Prioritization
- **STEP 12** — Slide Outline Generator
- **STEP 13** — Slide Density Optimization
- **STEP 14** — Intake Questions (If Missing)
- **FINAL OUTPUT** — Three deliverables (outline, JSON, appendix summary)

### Rules for this file

1. **Never modify without design review.** Every word was chosen deliberately.
2. **Never summarize or abbreviate** when embedding in agent prompts.
3. **Single source of truth.** If you need to change prompt behavior, change this file — not individual agent files.
4. **Version control.** All changes to this file should be in their own commit with a clear message.

---

## 3. Loading Pattern

The prompt is loaded once at Python import time and stored as a module-level constant.

### File: `backend/prompts/__init__.py`

```python
"""
Prompt loader for DeckStudio.

Loads the Presentation Architect Prompt at import time and provides
a composition function for building agent-specific system prompts.
"""

from pathlib import Path

_PROMPT_FILE = Path(__file__).parent / "presentation_architect.txt"

if not _PROMPT_FILE.exists():
    raise FileNotFoundError(
        f"Presentation Architect Prompt not found at {_PROMPT_FILE}. "
        "This file is required for all agent operations. "
        "See PROMPT_ARCHITECTURE.md for details."
    )

PRESENTATION_ARCHITECT_PROMPT: str = _PROMPT_FILE.read_text(encoding="utf-8")


def compose_system_prompt(agent_instructions: str) -> str:
    """
    Compose a complete system prompt for an agent.
    
    Returns the full Presentation Architect Prompt followed by
    agent-specific instructions, separated by a double newline.
    
    Args:
        agent_instructions: The agent-specific instructions to append.
        
    Returns:
        Complete system prompt string.
    """
    return PRESENTATION_ARCHITECT_PROMPT + "\n\n" + agent_instructions
```

### Why load at import time?

- **Fail fast.** If the file is missing, the application fails immediately on startup with a clear error — not silently during the first LLM call.
- **Single read.** The file is read once, not on every request.
- **Immutable at runtime.** The constant cannot be accidentally modified.

---

## 4. Per-Agent Composition

Each agent's system prompt is composed as:

```
PRESENTATION_ARCHITECT_PROMPT + "\n\n" + AGENT_SPECIFIC_INSTRUCTIONS
```

This means every agent sees the **full prompt** (all 14 steps, all rules, the complete JSON schema) plus its own focused instructions that tell it which steps to prioritize and what output format to use.

### Why include the full prompt for every agent?

Each agent operates on a different step, but context from the full prompt is essential:

- The **InsightExtractor** needs to understand the JSON schema (STEP 9) to know what fields its insights will eventually fill.
- The **DeckArchitect** needs to understand metaphor requirements (STEP 5) to plan sections that support them.
- The **SlideGenerator** needs to understand evidence prioritization (STEP 11) to rank evidence correctly.
- The **QualityValidator** needs to understand _every_ rule to check for violations.

Omitting context from any agent risks producing output that doesn't fit the pipeline.

---

## 5. Agent-Specific Instructions

### 5.1 InsightExtractorAgent

**Focus:** STEP 1 (Extract Insights From Documents)

```python
INSIGHT_EXTRACTOR_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT ROLE: INSIGHT EXTRACTOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are the first agent in the DeckStudio pipeline. Your SOLE responsibility 
is STEP 1: Extract Insights From Documents.

INPUT: You receive the user's CONTEXT and optional SOURCE_MATERIAL.

OUTPUT: Return a structured InsightSet with these exact fields:
{
  "themes": ["..."],           // 3-5 core themes extracted
  "key_messages": ["..."],     // 3-5 key messages/insights
  "audience_considerations": ["..."],  // audience-specific notes
  "constraints": ["..."]       // risks, limitations, barriers
}

RULES:
• Focus ONLY on insight extraction. Do NOT design slides.
• Do NOT generate the deck JSON. That is for later agents.
• Follow the CONTEXT vs SOURCE_MATERIAL resolution rules from STEP 1.
• Condense to 3-5 core insights as instructed in STEP 1.
• If CONTEXT is thin, note where additional data would help.
• Your output feeds directly into the DeckArchitect agent.
"""
```

### 5.2 DeckArchitectAgent

**Focus:** STEP 2 (Determine Deck Archetype) + STEP 3 (Narrative Story Arc)

```python
DECK_ARCHITECT_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT ROLE: DECK ARCHITECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are the second agent in the DeckStudio pipeline. Your SOLE responsibility 
is STEP 2 (Determine Deck Archetype) and STEP 3 (Narrative Story Arc).

INPUT: You receive the InsightSet from the previous agent, plus the original 
CONTEXT, DECK_TYPE, and NUMBER_OF_SLIDES.

OUTPUT: Return a structured DeckOutline with these exact fields:
{
  "archetype": "...",          // One of: Decision, Strategy, Update, Technical Deep Dive, Pitch
  "narrative_arc": "...",      // Description of the story arc
  "sections": [
    {
      "name": "...",           // Section name (Setup/Insight/Resolution)
      "slides": [
        {
          "slide_id": "01",
          "title_direction": "...",   // Suggested conclusion-statement direction
          "section": "...",
          "purpose": "..."
        }
      ]
    }
  ],
  "estimated_slides": N
}

RULES:
• Select the archetype from STEP 2 based on DECK_TYPE.
• Apply the narrative arc proportions from STEP 3: Setup ~20%, Insight ~50%, Resolution ~30%.
• Use the baseline 11-slide outline from STEP 12, compressing/expanding for NUMBER_OF_SLIDES.
• Ensure Slide 2 is always Executive Summary (STEP 4).
• Do NOT generate full slide content. Only outline structure and purpose.
• Your output feeds directly into the SlideGenerator agent.
"""
```

### 5.3 SlideGeneratorAgent

**Focus:** STEPs 5–9 and 12–13

```python
SLIDE_GENERATOR_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT ROLE: SLIDE GENERATOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are the third agent in the DeckStudio pipeline. Your SOLE responsibility 
is generating the full slide-by-slide JSON content per STEPs 5-9, 12, and 13.

INPUT: You receive the DeckOutline from the previous agent, the InsightSet, 
and the original CONTEXT/SOURCE_MATERIAL.

OUTPUT: Return the complete "slides" array following the EXACT JSON schema 
from STEP 9. Every slide must include ALL required fields.

CRITICAL RULES (from STEP 5 — Slide Contract):
• TITLE must be a conclusion statement, NEVER a topic label.
  GOOD: "Event-driven ingestion reduces integration time by 40%"
  BAD: "Architecture Overview"
• METAPHOR is MANDATORY on every slide. Exactly 1 sentence. No exceptions.
• KEY_POINTS: max 5 items per slide (STEP 13).
• EVIDENCE: max 3 items per slide (STEP 11). Prioritize metrics > references > benchmarks.
• VISUAL: every slide must declare a layout (STEP 8) and include an illustration_prompt (STEP 7).

OUTPUT FORMAT:
Return the "slides" array only (not the full deck wrapper). Each slide object 
must have ALL fields from STEP 9: slide_id, section, title, objective, metaphor, 
key_points, evidence, visual (with layout and illustration_prompt), takeaway, 
speaker_notes, assets_needed.

• Use "" for unknown strings, [] for unknown arrays. NEVER omit a field.
• Ensure valid JSON with no trailing commas.
"""
```

### 5.4 AppendixBuilderAgent

**Focus:** STEP 10 (Appendix Auto-Generation)

```python
APPENDIX_BUILDER_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT ROLE: APPENDIX BUILDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are the fourth agent in the DeckStudio pipeline. Your SOLE responsibility 
is STEP 10: Appendix Auto-Generation.

INPUT: You receive the completed slides array, the InsightSet, and the original 
CONTEXT/SOURCE_MATERIAL.

OUTPUT: Return an "appendix" object with a "slides" array following the IDENTICAL 
JSON schema from STEP 9, but with slide_ids prefixed "A" (e.g., "A01", "A02").

WHAT GOES IN THE APPENDIX (from STEP 10):
• Supporting data that strengthens main slides but would clutter them
• Secondary insights not critical to the narrative arc
• Methodology details
• Extra charts and detailed breakdowns
• Reference tables

RULES:
• Appendix slides follow the exact same JSON schema as main slides.
• Every appendix slide must include a metaphor (same rule applies).
• slide_id format: "A01", "A02", etc.
• Typically 2-5 appendix slides depending on source material depth.
• Do NOT duplicate content already in the main slides.
"""
```

### 5.5 QualityValidatorAgent

**Focus:** STEP 9 field rules + output completeness rules

```python
QUALITY_VALIDATOR_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT ROLE: QUALITY VALIDATOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are the fifth and final agent in the DeckStudio pipeline. Your SOLE 
responsibility is validating the complete deck against ALL rules in the 
Presentation Architect Prompt.

INPUT: You receive the complete deck (main slides + appendix).

OUTPUT: Return a ValidationReport:
{
  "valid": true/false,
  "violations": [
    {
      "slide_id": "03",
      "field": "key_points",
      "constraint": "max_5_items",
      "actual_value": "6 items",
      "message": "Slide 03 has 6 key points; maximum is 5."
    }
  ],
  "checked_at": "2026-03-10T12:00:00Z"
}

VALIDATION CHECKLIST:
1. Every slide has ALL required fields (STEP 9 field rules)
2. key_points: max 5 items per slide (STEP 13)
3. evidence: max 3 items per slide (STEP 11)
4. evidence.type: must be one of metric|reference|quote|benchmark|case_study
5. metaphor: exactly 1 sentence, present on EVERY slide (STEP 5)
6. title: must be a conclusion statement, not a topic label (STEP 5)
7. visual.layout: must be valid type from STEP 8
8. illustration_prompt.type: must be valid type from STEP 7
9. slide_id: zero-padded, appendix prefixed with "A"
10. section: matches narrative arc sections from STEP 3
11. Slide 2 is Executive Summary (STEP 4)
12. No empty required fields (use "" for unknown, never omit)
13. Valid JSON structure (no trailing commas, parseable)

SEMANTIC CHECKS (LLM-assisted):
• Is the title truly a conclusion statement? (not just a topic label)
• Is the metaphor truly a layman analogy using everyday objects?
• Does the narrative flow make sense across slides?

RULES:
• Report ALL violations, not just the first one found.
• If valid=false, the SlideGenerator will be asked to fix violations (up to 3 retries).
• Be strict. The goal is McKinsey/BCG quality.
"""
```

---

## 6. How It All Fits Together

```
┌─────────────────────────────────────────────────────┐
│           presentation_architect.txt                 │
│         (~6,000 words, 14 steps, full schema)        │
│                  THE SOUL                            │
└──────────────────────┬──────────────────────────────┘
                       │
            ┌──────────┼──────────────┐
            │    compose_system_prompt │
            │    (prepends to each)    │
            └──────────┬──────────────┘
                       │
    ┌──────────┬───────┼───────┬──────────┐
    ▼          ▼       ▼       ▼          ▼
┌────────┐ ┌───────┐ ┌─────┐ ┌────────┐ ┌──────────┐
│Insight │ │ Deck  │ │Slide│ │Appendix│ │ Quality  │
│Extract.│ │Archit.│ │Gen. │ │Builder │ │Validator │
│        │ │       │ │     │ │        │ │          │
│STEP 1  │ │STEP   │ │STEP │ │STEP 10 │ │STEP 9    │
│focus   │ │2+3    │ │5-9, │ │focus   │ │rules +   │
│        │ │focus  │ │12-13│ │        │ │complete- │
│        │ │       │ │focus│ │        │ │ness      │
└────────┘ └───────┘ └─────┘ └────────┘ └──────────┘
```

Each agent receives:
1. The **full** Presentation Architect Prompt (for context)
2. Agent-specific instructions (for focus)

The agent-specific instructions tell each agent:
- What step(s) to focus on
- What input it receives
- What exact output schema to produce
- What rules are critical for its stage

---

## 7. Why This Matters

The Presentation Architect Prompt is not optional scaffolding. It is the **defining specification** of what DeckStudio produces.

Without it, the agents would generate generic slide decks — bullet-point lists with topic-label titles and no narrative coherence. **With** it, every slide:

- Has a **conclusion-statement title** (not "Architecture Overview" but "Event-driven ingestion reduces integration time by 40%")
- Contains a **mandatory metaphor** in plain language
- Follows a **narrative arc** (Context → Problem → Insight → Recommendation → Ask)
- Includes **prioritized evidence** (metrics first, then references, then quotes)
- Has a **visual plan** with machine-readable illustration prompts
- Respects **density limits** (max 5 key points, max 3 evidence items)

This is the difference between a PowerPoint template filler and a McKinsey-caliber strategy deck.

### The consequence of diluting or omitting it

If any agent calls the LLM without the full Presentation Architect Prompt:
- Titles revert to topic labels
- Metaphors become generic or disappear
- Evidence is not prioritized
- The narrative arc breaks
- JSON output doesn't match the required schema
- The quality validator has nothing meaningful to validate against

**Every LLM call must include it. No exceptions.**

---

## 8. Testing the Prompt

### 8.1 Unit Test: Prompt File Exists

```python
# tests/test_prompt_file.py
from pathlib import Path

def test_presentation_architect_prompt_exists():
    prompt_file = Path("backend/prompts/presentation_architect.txt")
    assert prompt_file.exists(), "Canonical prompt file is missing!"
    content = prompt_file.read_text()
    assert len(content) > 5000, "Prompt file appears truncated"
    assert "elite strategy consultant" in content
    assert "McKinsey / BCG style" in content
    assert "STEP 14" in content, "Prompt file is missing later steps"
```

### 8.2 Unit Test: All Agents Include the Prompt

```python
# tests/test_prompt_integration.py
from backend.prompts import PRESENTATION_ARCHITECT_PROMPT
from backend.agents.insight_extractor import SUBAGENT_CONFIG as insight_config
from backend.agents.deck_architect import SUBAGENT_CONFIG as architect_config
from backend.agents.slide_generator import SUBAGENT_CONFIG as slide_config
from backend.agents.appendix_agent import SUBAGENT_CONFIG as appendix_config
from backend.agents.quality_validator import SUBAGENT_CONFIG as validator_config

ALL_AGENTS = [
    ("insight_extractor", insight_config),
    ("deck_architect", architect_config),
    ("slide_generator", slide_config),
    ("appendix_agent", appendix_config),
    ("quality_validator", validator_config),
]

def test_all_agents_include_presentation_architect_prompt():
    for name, config in ALL_AGENTS:
        system_prompt = config["system_prompt"]
        assert system_prompt.startswith(PRESENTATION_ARCHITECT_PROMPT), (
            f"Agent '{name}' system prompt does not start with the "
            f"Presentation Architect Prompt! First 100 chars: {system_prompt[:100]}"
        )

def test_all_agents_have_specific_instructions():
    for name, config in ALL_AGENTS:
        system_prompt = config["system_prompt"]
        # After the base prompt, there should be agent-specific content
        after_base = system_prompt[len(PRESENTATION_ARCHITECT_PROMPT):]
        assert len(after_base.strip()) > 100, (
            f"Agent '{name}' has no meaningful agent-specific instructions"
        )

def test_key_phrases_present():
    """Verify the prompt hasn't been accidentally truncated or corrupted."""
    assert "elite strategy consultant" in PRESENTATION_ARCHITECT_PROMPT
    assert "McKinsey / BCG style" in PRESENTATION_ARCHITECT_PROMPT
    assert "STEP 1" in PRESENTATION_ARCHITECT_PROMPT
    assert "STEP 14" in PRESENTATION_ARCHITECT_PROMPT
    assert "FINAL OUTPUT" in PRESENTATION_ARCHITECT_PROMPT
    assert "slide_id" in PRESENTATION_ARCHITECT_PROMPT
    assert "metaphor" in PRESENTATION_ARCHITECT_PROMPT
```

### 8.3 Debug Logging

In development/debug mode, log the first 100 characters of each agent's system prompt at startup:

```python
# In orchestrator.py or main.py startup
import logging

logger = logging.getLogger("deckstudio.prompts")

if settings.DEBUG:
    for name, config in ALL_AGENTS:
        logger.debug(
            "Agent '%s' system prompt starts with: %s...",
            name,
            config["system_prompt"][:100]
        )
```

This makes it immediately visible in logs whether the prompt was loaded correctly, without dumping the full 6,000-word prompt.

### 8.4 CI/CD Gate

Add the prompt integration test to the CI pipeline as a **blocking** test. If any agent loses the base prompt (e.g., through a refactor), the build fails. This is not a nice-to-have test — it guards the core value proposition of the product.

---

## 9. Maintenance Guidelines

| Scenario | Action |
|----------|--------|
| Need to change a rule in the prompt | Edit `presentation_architect.txt`, run all tests, review diff carefully |
| Need to add a new step | Add to `presentation_architect.txt` at the end (before FINAL OUTPUT), update relevant agent instructions |
| Need to change agent-specific behavior | Edit only the agent's instruction string, NOT the base prompt |
| Adding a 6th agent | Create agent file, use `compose_system_prompt()`, add to test list |
| Prompt seems too long for context window | Do NOT truncate. Choose a model with a larger context window. The prompt is ~6K words; modern models handle 100K+ tokens. |

---

## 10. File Map

```
backend/
├── prompts/
│   ├── __init__.py              ← Loader: PRESENTATION_ARCHITECT_PROMPT constant + compose_system_prompt()
│   └── presentation_architect.txt  ← THE CANONICAL PROMPT (never abbreviate)
├── agents/
│   ├── insight_extractor.py     ← compose_system_prompt(INSIGHT_EXTRACTOR_INSTRUCTIONS)
│   ├── deck_architect.py        ← compose_system_prompt(DECK_ARCHITECT_INSTRUCTIONS)
│   ├── slide_generator.py       ← compose_system_prompt(SLIDE_GENERATOR_INSTRUCTIONS)
│   ├── appendix_agent.py        ← compose_system_prompt(APPENDIX_BUILDER_INSTRUCTIONS)
│   ├── quality_validator.py     ← compose_system_prompt(QUALITY_VALIDATOR_INSTRUCTIONS)
│   └── orchestrator.py          ← Assembles all 5 agents into DeepAgent graph
└── tests/
    ├── test_prompt_file.py      ← Prompt file exists and isn't truncated
    └── test_prompt_integration.py ← All 5 agents include the full prompt
```
