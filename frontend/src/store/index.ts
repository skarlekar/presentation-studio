/**
 * Global Zustand store for DeckStudio.
 *
 * Single store split into logical slices:
 * - sessionSlice: pipeline session state
 * - deckSlice: generated deck + slide selection
 * - uiSlice: tab navigation, modals, display toggles
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type {
  AgentStep,
  DeckRequest,
  DeckEnvelope,
  SessionStatusResponse,
  Checkpoint,
  PipelineStatus,
  Slide,
  Tab,
} from '@/types'

// ─────────────────────────────────────────────────────────────────────────────
// State shape
// ─────────────────────────────────────────────────────────────────────────────

interface SessionSlice {
  sessionId: string | null
  status: PipelineStatus | null
  currentStage: string | null
  progressPct: number
  checkpoint: Checkpoint | null
  error: string | null
  isPolling: boolean
  lastRequest: DeckRequest | null
  agentSteps: AgentStep[]
}

interface DeckSlice {
  envelope: DeckEnvelope | null
  selectedSlideId: string | null
  editingSlideId: string | null
}

interface UiSlice {
  activeTab: Tab
  showSpeakerNotes: boolean
  showAppendix: boolean
  checkpointModalOpen: boolean
  exportResult: {
    filename: string
    version: number
    saved_at: string
    size_bytes: number
  } | null
}

interface ApiKeySlice {
  apiKey: string | null          // User-supplied Anthropic API key
  apiKeyConfigured: boolean      // True if key is pre-configured in server env
  apiKeyChecked: boolean         // True after health check has been performed
}

// ─────────────────────────────────────────────────────────────────────────────
// Actions
// ─────────────────────────────────────────────────────────────────────────────

interface Actions {
  // Session
  startSession: (sessionId: string, request: DeckRequest) => void
  updateFromStatus: (status: SessionStatusResponse) => void
  setPolling: (polling: boolean) => void
  setEnvelope: (envelope: DeckEnvelope) => void
  setAgentSteps: (steps: AgentStep[]) => void
  resetSession: () => void

  // Deck / slide editing
  selectSlide: (slideId: string | null) => void
  setEditingSlide: (slideId: string | null) => void
  updateSlideInStore: (updatedSlide: Slide) => void

  // UI
  setTab: (tab: Tab) => void
  toggleSpeakerNotes: () => void
  toggleAppendix: () => void
  openCheckpointModal: () => void
  closeCheckpointModal: () => void
  setExportResult: (result: UiSlice['exportResult']) => void

  // API key
  setApiKey: (key: string) => void
  setApiKeyStatus: (configured: boolean) => void
  clearApiKey: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

const initialApiKeySlice: ApiKeySlice = {
  apiKey: typeof sessionStorage !== 'undefined'
    ? sessionStorage.getItem('deckstudio_api_key')
    : null,
  apiKeyConfigured: false,
  apiKeyChecked: false,
}

const initialSessionSlice: SessionSlice = {
  sessionId: null,
  status: null,
  currentStage: null,
  progressPct: 0,
  checkpoint: null,
  error: null,
  isPolling: false,
  lastRequest: null,
  agentSteps: [],
}

const initialDeckSlice: DeckSlice = {
  envelope: null,
  selectedSlideId: null,
  editingSlideId: null,
}

const initialUiSlice: UiSlice = {
  activeTab: 'intake',
  showSpeakerNotes: false,
  showAppendix: false,
  checkpointModalOpen: false,
  exportResult: null,
}

export const useStore = create<SessionSlice & DeckSlice & UiSlice & ApiKeySlice & Actions>()(
  persist(
    (set, get) => ({
  // ── Initial state ──────────────────────────────────────────────────────────
  ...initialSessionSlice,
  ...initialDeckSlice,
  ...initialUiSlice,
  ...initialApiKeySlice,

  // ── Session actions ────────────────────────────────────────────────────────

  startSession: (sessionId, request) =>
    set({
      sessionId,
      status: 'pending',
      currentStage: null,
      progressPct: 0,
      checkpoint: null,
      error: null,
      isPolling: true,
      lastRequest: request,
      envelope: null,
      selectedSlideId: null,
      editingSlideId: null,
      exportResult: null,
      activeTab: 'intake',
      agentSteps: [],
    }),

  updateFromStatus: (statusResp) => {
    const checkpoint = statusResp.checkpoint ?? statusResp.active_checkpoint ?? null
    const shouldOpenModal =
      statusResp.status === 'awaiting_approval' &&
      checkpoint !== null &&
      !get().checkpointModalOpen

    const updates: Partial<SessionSlice & UiSlice> = {
      status: statusResp.status as PipelineStatus,
      currentStage: statusResp.current_stage ?? null,
      progressPct: statusResp.progress_pct ?? 0,
      checkpoint,
      error: statusResp.error ?? null,
      checkpointModalOpen: shouldOpenModal ? true : get().checkpointModalOpen,
    }

    // Update agent steps from status response if present
    if (statusResp.agent_steps && statusResp.agent_steps.length > 0) {
      updates.agentSteps = statusResp.agent_steps
    }

    set(updates)

    // Auto-switch to Gallery tab when deck is complete
    if (
      (statusResp.status === 'completed' || statusResp.status === 'complete') &&
      get().activeTab === 'intake'
    ) {
      set({ activeTab: 'gallery', isPolling: false })
    }
  },

  setPolling: (polling) => set({ isPolling: polling }),

  setEnvelope: (envelope) =>
    set({
      envelope,
      status: 'completed',
      isPolling: false,
      activeTab: 'gallery',
    }),

  setAgentSteps: (steps) => set({ agentSteps: steps }),

  resetSession: () =>
    set({
      ...initialSessionSlice,
      ...initialDeckSlice,
      activeTab: 'intake',
      exportResult: null,
      checkpointModalOpen: false,
      agentSteps: [],
    }),

  // ── Deck / slide editing actions ───────────────────────────────────────────

  selectSlide: (slideId) => set({ selectedSlideId: slideId }),

  setEditingSlide: (slideId) => set({ editingSlideId: slideId }),

  updateSlideInStore: (updatedSlide) => {
    const { envelope } = get()
    if (!envelope?.deck) return

    // Update in main slides
    const slides = envelope.deck.slides.map((s) =>
      s.slide_id === updatedSlide.slide_id ? updatedSlide : s,
    )

    // Update in appendix slides
    const appendixSlides = envelope.deck.appendix.slides.map((s) =>
      s.slide_id === updatedSlide.slide_id ? updatedSlide : s,
    )

    set({
      envelope: {
        ...envelope,
        deck: {
          ...envelope.deck,
          slides,
          appendix: {
            ...envelope.deck.appendix,
            slides: appendixSlides,
          },
        },
      },
    })
  },

  // ── UI actions ─────────────────────────────────────────────────────────────

  setTab: (tab) => set({ activeTab: tab }),

  toggleSpeakerNotes: () => set((s) => ({ showSpeakerNotes: !s.showSpeakerNotes })),

  toggleAppendix: () => set((s) => ({ showAppendix: !s.showAppendix })),

  openCheckpointModal: () => set({ checkpointModalOpen: true }),

  closeCheckpointModal: () => set({ checkpointModalOpen: false }),

  setExportResult: (result) => set({ exportResult: result }),

  // ── API key actions ────────────────────────────────────────────────────────

  setApiKey: (key) => {
    // Store in sessionStorage (cleared on tab close — more secure than localStorage)
    try { sessionStorage.setItem('deckstudio_api_key', key) } catch { /* ignore */ }
    set({ apiKey: key })
  },

  setApiKeyStatus: (configured) => set({ apiKeyConfigured: configured, apiKeyChecked: true }),

  clearApiKey: () => {
    try { sessionStorage.removeItem('deckstudio_api_key') } catch { /* ignore */ }
    set({ apiKey: null })
  },
}),
    {
      name: 'deckstudio-session',
      storage: createJSONStorage(() => localStorage),
      // Only persist what matters across page refreshes — not polling/UI state
      partialize: (state) => ({
        sessionId: state.sessionId,
        envelope: state.envelope,
        status: state.status === 'running' ? null : state.status,  // don't restore mid-run
        lastRequest: state.lastRequest,
        agentSteps: state.agentSteps,
      }),
    }
  )
)

// ── Selectors ──────────────────────────────────────────────────────────────────

/** Returns the currently selected Slide (main or appendix), or null. */
export function useSelectedSlide() {
  return useStore((s) => {
    if (!s.selectedSlideId || !s.envelope?.deck) return null
    const all = [...s.envelope.deck.slides, ...s.envelope.deck.appendix.slides]
    return all.find((sl) => sl.slide_id === s.selectedSlideId) ?? null
  })
}

/** Returns true if the pipeline is in a terminal state. */
export function useIsTerminal() {
  return useStore((s) =>
    s.status !== null &&
    ['completed', 'complete', 'failed', 'cancelled', 'rejected'].includes(s.status),
  )
}

/** Returns the active checkpoint, if any. */
export function useCheckpoint() {
  return useStore((s) => s.checkpoint)
}
