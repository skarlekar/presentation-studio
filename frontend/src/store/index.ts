/**
 * Global Zustand store for DeckStudio.
 *
 * Single store split into logical slices:
 * - sessionSlice: active pipeline session state
 * - deckSlice: active deck + slide selection
 * - librarySlice: all completed/in-progress decks (persisted)
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
// Deck Library
// ─────────────────────────────────────────────────────────────────────────────

export interface DeckLibraryEntry {
  sessionId: string
  title: string
  deckType: string
  status: PipelineStatus | 'completed'
  envelope: DeckEnvelope
  totalSlides: number
  appendixSlides: number
  createdAt: string    // ISO string
  exportedAt?: string  // ISO string, set on first export
}

interface LibrarySlice {
  library: DeckLibraryEntry[]
}

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
  apiKey: string | null
  apiKeyConfigured: boolean
  apiKeyChecked: boolean
}

// ─────────────────────────────────────────────────────────────────────────────
// Actions
// ─────────────────────────────────────────────────────────────────────────────

interface Actions {
  // Session
  startSession: (sessionId: string, request: DeckRequest) => void
  setCompletedSession: (sessionId: string, envelope: DeckEnvelope) => void
  updateFromStatus: (status: SessionStatusResponse) => void
  setPolling: (polling: boolean) => void
  setEnvelope: (envelope: DeckEnvelope) => void
  setAgentSteps: (steps: AgentStep[]) => void
  resetSession: () => void

  // Deck Library
  upsertLibraryEntry: (entry: DeckLibraryEntry) => void
  removeFromLibrary: (sessionId: string) => void
  switchToDeck: (entry: DeckLibraryEntry) => void
  markExported: (sessionId: string) => void

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
  setError: (error: string | null) => void
  setSessionId: (sessionId: string) => void

  // API key
  setApiKey: (key: string) => void
  setApiKeyStatus: (configured: boolean) => void
  clearApiKey: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Initial state
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

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function envelopeToLibraryEntry(
  sessionId: string,
  envelope: DeckEnvelope,
  exportedAt?: string,
): DeckLibraryEntry {
  const deck = envelope.deck
  return {
    sessionId,
    title: deck?.title ?? 'Untitled Deck',
    deckType: deck?.type ?? '',
    status: 'completed',
    envelope,
    totalSlides: deck?.slides?.length ?? 0,
    appendixSlides: deck?.appendix?.slides?.length ?? 0,
    createdAt: envelope.created_at ?? new Date().toISOString(),
    exportedAt,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

export const useStore = create<SessionSlice & DeckSlice & LibrarySlice & UiSlice & ApiKeySlice & Actions>()(
  persist(
    (set, get) => ({
      // ── Initial state ────────────────────────────────────────────────────────
      ...initialSessionSlice,
      ...initialDeckSlice,
      ...initialUiSlice,
      ...initialApiKeySlice,
      library: [],

      // ── Session actions ──────────────────────────────────────────────────────

      startSession: (sessionId, request) =>
        set({
          // Start fresh active-session state — library untouched
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

      setCompletedSession: (sessionId, envelope) => {
        const entry = envelopeToLibraryEntry(sessionId, envelope)
        set((s) => ({
          sessionId,
          status: 'completed',
          isPolling: false,
          envelope,
          error: null,
          exportResult: null,
          checkpoint: null,
          library: upsertEntry(s.library, entry),
        }))
      },

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

        if (statusResp.agent_steps && statusResp.agent_steps.length > 0) {
          updates.agentSteps = statusResp.agent_steps
        }

        set(updates)

        if (
          (statusResp.status === 'completed' || statusResp.status === 'complete') &&
          get().activeTab === 'intake'
        ) {
          set({ activeTab: 'gallery', isPolling: false })
        }
      },

      setPolling: (polling) => set({ isPolling: polling }),

      setEnvelope: (envelope) => {
        const { sessionId } = get()
        const entry = sessionId ? envelopeToLibraryEntry(sessionId, envelope) : null
        set((s) => ({
          envelope,
          status: 'completed',
          isPolling: false,
          activeTab: 'gallery',
          library: entry ? upsertEntry(s.library, entry) : s.library,
        }))
      },

      setAgentSteps: (steps) => set({ agentSteps: steps }),

      resetSession: () =>
        // Clear active session — library untouched
        set({
          ...initialSessionSlice,
          ...initialDeckSlice,
          activeTab: 'intake',
          exportResult: null,
          checkpointModalOpen: false,
          agentSteps: [],
        }),

      // ── Library actions ──────────────────────────────────────────────────────

      upsertLibraryEntry: (entry) =>
        set((s) => ({ library: upsertEntry(s.library, entry) })),

      removeFromLibrary: (sessionId) =>
        set((s) => ({ library: s.library.filter((e) => e.sessionId !== sessionId) })),

      switchToDeck: (entry) =>
        set({
          sessionId: entry.sessionId,
          status: 'completed',
          isPolling: false,
          envelope: entry.envelope,
          selectedSlideId: null,
          editingSlideId: null,
          exportResult: null,
          error: null,
          checkpoint: null,
          activeTab: 'gallery',
        }),

      markExported: (sessionId) =>
        set((s) => ({
          library: s.library.map((e) =>
            e.sessionId === sessionId
              ? { ...e, exportedAt: new Date().toISOString() }
              : e,
          ),
        })),

      // ── Deck / slide editing actions ─────────────────────────────────────────

      selectSlide: (slideId) => set({ selectedSlideId: slideId }),
      setEditingSlide: (slideId) => set({ editingSlideId: slideId }),

      updateSlideInStore: (updatedSlide) => {
        const { envelope } = get()
        if (!envelope?.deck) return

        const slides = envelope.deck.slides.map((s) =>
          s.slide_id === updatedSlide.slide_id ? updatedSlide : s,
        )
        const appendixSlides = envelope.deck.appendix.slides.map((s) =>
          s.slide_id === updatedSlide.slide_id ? updatedSlide : s,
        )

        set({
          envelope: {
            ...envelope,
            deck: {
              ...envelope.deck,
              slides,
              appendix: { ...envelope.deck.appendix, slides: appendixSlides },
            },
          },
        })
      },

      // ── UI actions ───────────────────────────────────────────────────────────

      setTab: (tab) => set({ activeTab: tab }),
      toggleSpeakerNotes: () => set((s) => ({ showSpeakerNotes: !s.showSpeakerNotes })),
      toggleAppendix: () => set((s) => ({ showAppendix: !s.showAppendix })),
      openCheckpointModal: () => set({ checkpointModalOpen: true }),
      closeCheckpointModal: () => set({ checkpointModalOpen: false }),
      setExportResult: (result) => set({ exportResult: result }),
      setError: (error) => set({ error }),
      setSessionId: (sessionId) => set({ sessionId }),

      // ── API key actions ──────────────────────────────────────────────────────

      setApiKey: (key) => {
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
      partialize: (state) => ({
        sessionId: state.sessionId,
        envelope: state.envelope,
        status: state.status === 'running' ? null : state.status,
        lastRequest: state.lastRequest,
        agentSteps: state.agentSteps,
        library: state.library,   // ← persist the full deck library
      }),
    }
  )
)

// ── Pure helper ────────────────────────────────────────────────────────────────

function upsertEntry(
  library: DeckLibraryEntry[],
  entry: DeckLibraryEntry,
): DeckLibraryEntry[] {
  const idx = library.findIndex((e) => e.sessionId === entry.sessionId)
  if (idx === -1) return [entry, ...library]  // newest first
  const updated = [...library]
  updated[idx] = { ...updated[idx], ...entry }
  return updated
}

// ── Selectors ──────────────────────────────────────────────────────────────────

export function useSelectedSlide() {
  return useStore((s) => {
    if (!s.selectedSlideId || !s.envelope?.deck) return null
    const all = [...s.envelope.deck.slides, ...s.envelope.deck.appendix.slides]
    return all.find((sl) => sl.slide_id === s.selectedSlideId) ?? null
  })
}

export function useIsTerminal() {
  return useStore((s) =>
    s.status !== null &&
    ['completed', 'complete', 'failed', 'cancelled', 'rejected'].includes(s.status),
  )
}

export function useCheckpoint() {
  return useStore((s) => s.checkpoint)
}
