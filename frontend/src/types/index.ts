// ─────────────────────────────────────────────────────────────────────────────
// Enums — must match backend exactly
// ─────────────────────────────────────────────────────────────────────────────

export type DeckType =
  | 'Decision Deck'
  | 'Strategy Deck'
  | 'Update Deck'
  | 'Technical Deep Dive'
  | 'Pitch Deck'

export type DecisionInformAsk = 'Decision' | 'Inform' | 'Ask'

export type PipelineStatus =
  | 'pending'
  | 'running'
  | 'extracting_insights'
  | 'generating_outline'
  | 'awaiting_approval'
  | 'awaiting_outline_approval'
  | 'generating_slides'
  | 'awaiting_review_approval'
  | 'validating'
  | 'complete'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rejected'

export type CheckpointStatus = 'pending' | 'approved' | 'rejected' | 'skipped'

export type EvidenceType = 'metric' | 'reference' | 'quote' | 'benchmark' | 'case_study'

export type LayoutType =
  | 'title'
  | 'two-column'
  | 'chart'
  | 'timeline'
  | 'table'
  | 'quote'
  | 'full-bleed visual'
  | 'framework diagram'

export type VisualType =
  | 'process-diagram'
  | 'architecture-diagram'
  | 'data-chart'
  | 'comparison-table'
  | 'timeline'
  | 'framework'
  | 'matrix'
  | 'before-after'

// ─────────────────────────────────────────────────────────────────────────────
// Evidence
// ─────────────────────────────────────────────────────────────────────────────

export interface EvidenceItem {
  type: EvidenceType
  detail: string
  source?: string | null
}

// ─────────────────────────────────────────────────────────────────────────────
// Visual
// ─────────────────────────────────────────────────────────────────────────────

export interface IllustrationPrompt {
  type: VisualType
  description: string
  alt_text: string
}

export interface Visual {
  layout: LayoutType
  illustration_prompt: IllustrationPrompt
}

// ─────────────────────────────────────────────────────────────────────────────
// Slide
// ─────────────────────────────────────────────────────────────────────────────

export interface Slide {
  slide_id: string
  section: string
  title: string
  objective: string
  metaphor: string
  key_points: string[]
  evidence: EvidenceItem[]
  visual: Visual
  takeaway: string
  speaker_notes: string
  assets_needed: string[]
}

// ─────────────────────────────────────────────────────────────────────────────
// Deck
// ─────────────────────────────────────────────────────────────────────────────

export interface Appendix {
  slides: Slide[]
}

export interface Deck {
  title: string
  type: string
  audience: string
  tone: string
  decision_inform_ask: string
  context: string
  source_material_provided: boolean
  total_slides: number
  slides: Slide[]
  appendix: Appendix
}

export interface DeckEnvelope {
  session_id: string
  run_id?: string | null
  status: PipelineStatus
  deck: Deck | null
  error?: string | null
  created_at: string
  completed_at?: string | null
}

// ─────────────────────────────────────────────────────────────────────────────
// Checkpoints
// ─────────────────────────────────────────────────────────────────────────────

export interface Checkpoint {
  checkpoint_id: string
  session_id?: string
  stage: string
  stage_index: number
  label: string
  status: CheckpointStatus
  payload?: Record<string, unknown>
  pending_input?: Record<string, unknown>
  preview?: Record<string, unknown> | null
  feedback?: string | null
  resolution?: string | null
  edits?: Record<string, unknown> | null
  created_at?: string
  resolved_at?: string | null
}

// ─────────────────────────────────────────────────────────────────────────────
// Agent Steps (pipeline progress tracking)
// ─────────────────────────────────────────────────────────────────────────────

export interface AgentStep {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string | null
  completed_at: string | null
  output_summary: string | null
}

// ─────────────────────────────────────────────────────────────────────────────
// Session status
// ─────────────────────────────────────────────────────────────────────────────

export interface SessionStatusResponse {
  session_id: string
  run_id?: string | null
  status: PipelineStatus
  current_stage?: string | null
  progress_pct?: number
  slides_generated?: number
  total_slides?: number
  checkpoint?: Checkpoint | null
  active_checkpoint?: Checkpoint | null
  error?: string | null
  agent_steps?: AgentStep[]
  created_at: string
  updated_at: string
}

// ─────────────────────────────────────────────────────────────────────────────
// API request types
// ─────────────────────────────────────────────────────────────────────────────

export interface DeckRequest {
  context?: string | null
  number_of_slides: number
  audience: string
  deck_type: DeckType
  decision_inform_ask: DecisionInformAsk
  tone: string
  source_material?: string | null
  must_include_sections?: string[] | null
  brand_style_guide?: string | null
  top_messages?: string[] | null
  known_metrics?: string[] | null
  /** Anthropic API key supplied by the user — only included when server has no env key */
  api_key?: string | null
  run_id?: string | null
}

export interface GenerateResponse {
  session_id: string
  status: string
  message?: string
  stream_url?: string
  poll_url?: string
}

export interface CheckpointApproveRequest {
  session_id?: string
  checkpoint_id?: string
  comment?: string | null
  edits?: Record<string, unknown> | null
}

export interface CheckpointRejectRequest {
  session_id?: string
  checkpoint_id?: string
  feedback: string
  slide_ids?: string[] | null
}

export interface SlideUpdateRequest {
  session_id: string
  slide_id: string
  field: string
  value: unknown
}

// ─────────────────────────────────────────────────────────────────────────────
// Validation
// ─────────────────────────────────────────────────────────────────────────────

export interface Violation {
  slide_id?: string | null
  field: string
  rule?: string
  constraint?: string
  message?: string
  severity?: 'error' | 'warning' | 'info'
  actual_value?: string
  value_preview?: string | null
}

export interface ValidationReport {
  session_id?: string
  passed: boolean
  valid?: boolean
  total_slides_checked: number
  violations: Violation[]
  warnings: number
  errors: number
}

// ─────────────────────────────────────────────────────────────────────────────
// UI state types
// ─────────────────────────────────────────────────────────────────────────────

export type Tab = 'intake' | 'gallery' | 'export'

export interface UIState {
  activeTab: Tab
  selectedSlideId: string | null
  showSpeakerNotes: boolean
  showAppendix: boolean
}
