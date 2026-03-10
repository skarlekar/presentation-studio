/**
 * Shared test fixtures — minimal valid objects matching backend schema.
 */
import type { Slide, Deck, DeckEnvelope, SessionStatusResponse, Checkpoint } from '@/types'

export const mockSlide: Slide = {
  slide_id: '01',
  section: 'Setup',
  title: 'Cloud migration reduces TCO by 40% within 18 months',
  objective: 'Make the audience understand the financial case for migration.',
  metaphor: 'Moving to the cloud is like switching from owning a car to using a car service — you pay for what you use.',
  key_points: [
    'Current on-prem costs $4.2M/year in maintenance',
    'Cloud target state: $2.5M/year',
    '40% reduction in total cost of ownership',
  ],
  evidence: [
    { type: 'metric', detail: '40% TCO reduction based on Gartner 2024 benchmark', source: 'Gartner 2024' },
    { type: 'case_study', detail: 'Similar firm achieved 35% reduction in 12 months', source: 'Internal' },
  ],
  visual: {
    layout: 'two-column',
    illustration_prompt: {
      type: 'data-chart',
      description: 'Bar chart comparing on-prem vs cloud costs over 3 years',
      alt_text: 'Cost comparison bar chart showing 40% reduction',
    },
  },
  takeaway: 'Migration pays for itself within 18 months based on current cost trajectory.',
  speaker_notes: 'Emphasize the payback period. CFO will ask about upfront investment.',
  assets_needed: ['cost-comparison-chart.png'],
}

export const mockAppendixSlide: Slide = {
  ...mockSlide,
  slide_id: 'A01',
  section: 'Appendix',
  title: 'Detailed cost breakdown by infrastructure component',
  metaphor: 'This is the receipt that itemizes exactly where every dollar of the TCO saving comes from.',
}

export const mockDeck: Deck = {
  title: 'Cloud Migration Business Case',
  type: 'Decision Deck',
  audience: 'C-suite executives',
  tone: 'Authoritative and data-driven',
  decision_inform_ask: 'Decision',
  context: 'We need approval to proceed with the cloud migration initiative.',
  source_material_provided: false,
  total_slides: 1,
  slides: [mockSlide],
  appendix: {
    slides: [mockAppendixSlide],
  },
}

export const mockEnvelope: DeckEnvelope = {
  session_id: 'test-session-123',
  status: 'completed',
  deck: mockDeck,
  error: null,
  created_at: '2026-03-10T18:00:00Z',
  completed_at: '2026-03-10T18:05:00Z',
}

export const mockCheckpoint: Checkpoint = {
  checkpoint_id: 'cp-abc-123',
  session_id: 'test-session-123',
  stage: 'insight_extractor',
  stage_index: 1,
  label: 'Confirm Core Insights',
  status: 'pending',
  pending_input: {
    core_problem: 'Legacy infrastructure is cost-prohibitive',
    key_insights: ['40% TCO reduction possible', 'Payback in 18 months'],
  },
  preview: {
    core_problem: 'Legacy infrastructure is cost-prohibitive',
  },
}

export const mockStatusRunning: SessionStatusResponse = {
  session_id: 'test-session-123',
  status: 'running',
  current_stage: 'insight_extractor',
  progress_pct: 20,
  created_at: '2026-03-10T18:00:00Z',
  updated_at: '2026-03-10T18:01:00Z',
}

export const mockStatusAwaiting: SessionStatusResponse = {
  session_id: 'test-session-123',
  status: 'awaiting_approval',
  current_stage: 'insight_extractor',
  progress_pct: 20,
  checkpoint: mockCheckpoint,
  created_at: '2026-03-10T18:00:00Z',
  updated_at: '2026-03-10T18:01:30Z',
}

export const mockStatusCompleted: SessionStatusResponse = {
  session_id: 'test-session-123',
  status: 'completed',
  current_stage: null,
  progress_pct: 100,
  created_at: '2026-03-10T18:00:00Z',
  updated_at: '2026-03-10T18:05:00Z',
}
