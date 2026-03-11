/**
 * GalleryPage — Tab 2: Slide gallery + right-panel editor.
 *
 * Three states:
 * 1. Active session with completed deck   → show slides + editor
 * 2. Pipeline running                     → show progress badge
 * 3. No active session                    → show previous exports for reload
 */
import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { useDeck } from '@/hooks/useDeck'
import AgentStatusBadge from '@/components/AgentStatusBadge'
import SlideCard from '@/components/SlideCard'
import SlideEditor from '@/components/SlideEditor'
import AppendixSection from '@/components/AppendixSection'
import { listAllExports, loadExport } from '@/api/client'

interface ExportEntry {
  filename: string
  session_id: string
  title: string
  deck_type: string
  total_slides: number
  appendix_slides: number
  saved_at: string
  size_bytes: number
}

export default function GalleryPage() {
  const { envelope, status, currentStage, progressPct, error, selectedSlideId } = useStore(useShallow((s) => ({
    envelope: s.envelope,
    status: s.status,
    currentStage: s.currentStage,
    progressPct: s.progressPct,
    error: s.error,
    selectedSlideId: s.selectedSlideId,
  })))
  const { approve_and_export } = useDeck()
  const setEnvelope = useStore(s => s.setEnvelope)
  const startSession = useStore(s => s.startSession)

  const [prevRuns, setPrevRuns] = useState<ExportEntry[]>([])
  const [loadingPrev, setLoadingPrev] = useState(false)
  const [loadingFile, setLoadingFile] = useState<string | null>(null)

  const isComplete = status === 'completed' || status === 'complete'
  const isRunning = status && !isComplete && status !== 'failed' && status !== 'rejected'
  const slides = envelope?.deck?.slides ?? []
  const deck = envelope?.deck

  // Load previous exports when there's no active deck
  useEffect(() => {
    if (isComplete && envelope) return  // already have a deck
    setLoadingPrev(true)
    listAllExports()
      .then(res => setPrevRuns(res.exports ?? []))
      .catch(() => setPrevRuns([]))
      .finally(() => setLoadingPrev(false))
  }, [isComplete, envelope])

  const handleLoadExport = async (entry: ExportEntry) => {
    setLoadingFile(entry.filename)
    try {
      const { envelope: loaded, sessionId } = await loadExport(entry.filename)
      // Restore into store as a completed session
      startSession(sessionId, {} as any)
      setEnvelope(loaded)
    } catch (err) {
      console.error('[GalleryPage] loadExport error:', err)
    } finally {
      setLoadingFile(null)
    }
  }

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleString() } catch { return iso }
  }

  // ── State: pipeline running ─────────────────────────────────────────────
  if (isRunning && !envelope) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <AgentStatusBadge
          status={status}
          stage={currentStage}
          progressPct={progressPct}
          error={error}
        />
      </div>
    )
  }

  // ── State: no active deck — show previous runs ──────────────────────────
  if (!isComplete || !envelope) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">🗂️</div>
          <h2 className="text-lg font-semibold text-gray-700 mb-1">No active deck</h2>
          <p className="text-sm text-gray-400">
            Start a new deck from the Intake tab, or reload a previous run below.
          </p>
        </div>

        {loadingPrev ? (
          <p className="text-center text-sm text-gray-400">Loading previous runs…</p>
        ) : prevRuns.length === 0 ? (
          <p className="text-center text-sm text-gray-400 italic">No previous exports found.</p>
        ) : (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Previous runs</h3>
            {prevRuns.map((entry) => (
              <div
                key={entry.filename}
                className="bg-white border border-gray-200 rounded-xl px-5 py-4 flex items-center justify-between gap-4 shadow-sm hover:border-brand-300 transition-colors"
              >
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{entry.title}</p>
                  <div className="flex gap-2 mt-1 flex-wrap">
                    <span className="text-xs text-gray-400">{entry.deck_type}</span>
                    <span className="text-xs text-gray-300">·</span>
                    <span className="text-xs text-gray-400">{entry.total_slides} slides + {entry.appendix_slides} appendix</span>
                    {entry.saved_at && (
                      <>
                        <span className="text-xs text-gray-300">·</span>
                        <span className="text-xs text-gray-400">{formatDate(entry.saved_at)}</span>
                      </>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleLoadExport(entry)}
                  disabled={loadingFile === entry.filename}
                  className="shrink-0 px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                >
                  {loadingFile === entry.filename ? '⏳ Loading…' : 'Load'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── State: deck loaded — show slide gallery + editor ────────────────────
  return (
    <div className="flex h-full">
      {/* ── Left: slide list ── */}
      <div className="w-96 shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50">
        {deck && (
          <div className="px-4 py-4 border-b border-gray-200 bg-white">
            <h2 className="font-bold text-gray-900 text-base leading-snug">{deck.title}</h2>
            <div className="flex gap-2 mt-1.5 flex-wrap">
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
                {deck.type}
              </span>
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
                {deck.total_slides} slides
              </span>
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
                {deck.tone}
              </span>
            </div>
            <button
              onClick={approve_and_export}
              className="mt-3 w-full py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition-colors flex items-center justify-center gap-1.5"
            >
              ✓ Approve &amp; Export
            </button>
          </div>
        )}

        <div className="p-4 space-y-3">
          {slides.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">No slides yet</div>
          ) : (
            <>
              {slides.map((slide) => (
                <SlideCard key={slide.slide_id} slide={slide} />
              ))}
              <AppendixSection />
            </>
          )}
        </div>
      </div>

      {/* ── Right: slide editor ── */}
      <div className="flex-1 min-w-0 overflow-hidden">
        {selectedSlideId ? (
          <SlideEditor />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm">
            <div className="text-center">
              <div className="text-4xl mb-3">←</div>
              <p>Select a slide to edit</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
