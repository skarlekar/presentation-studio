/**
 * GalleryPage — Tab 2: Deck library sidebar + slide gallery/editor.
 *
 * Left panel  — Library: all decks (completed + in-progress), sorted newest first.
 *               Includes remote exports discovered via /api/deck/exports/all.
 * Right panel — Active deck: slides + editor for the selected deck.
 */
import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import type { DeckLibraryEntry } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { useDeck } from '@/hooks/useDeck'
import AgentStatusBadge from '@/components/AgentStatusBadge'
import SlideCard from '@/components/SlideCard'
import SlideEditor from '@/components/SlideEditor'
import AppendixSection from '@/components/AppendixSection'
import { listAllExports, loadExport } from '@/api/client'

export default function GalleryPage() {
  const {
    envelope,
    status,
    sessionId,
    currentStage,
    progressPct,
    error,
    selectedSlideId,
    library,
  } = useStore(useShallow((s) => ({
    envelope: s.envelope,
    status: s.status,
    sessionId: s.sessionId,
    currentStage: s.currentStage,
    progressPct: s.progressPct,
    error: s.error,
    selectedSlideId: s.selectedSlideId,
    library: s.library,
  })))

  const { approve_and_export } = useDeck()
  const switchToDeck = useStore((s) => s.switchToDeck)
  const upsertLibraryEntry = useStore((s) => s.upsertLibraryEntry)
  const removeFromLibrary = useStore((s) => s.removeFromLibrary)
  const setTab = useStore((s) => s.setTab)

  const [loadingFile, setLoadingFile] = useState<string | null>(null)
  const [remoteSynced, setRemoteSynced] = useState(false)

  const isComplete = status === 'completed' || status === 'complete'
  const isRunning = status && !isComplete && status !== 'failed' &&
                    status !== 'cancelled' && status !== 'rejected'
  const slides = envelope?.deck?.slides ?? []
  const deck = envelope?.deck

  // ── Sync remote exports into the library (once per mount) ─────────────────
  useEffect(() => {
    if (remoteSynced) return
    setRemoteSynced(true)

    listAllExports()
      .then(({ exports }) => {
        const remoteIds = new Set(exports.map((e) => e.session_id).filter(Boolean))
        const localIds  = new Set(library.map((e) => e.sessionId))

        // Only fetch exports not already in local library
        const missing = exports.filter(
          (e) => e.session_id && !localIds.has(e.session_id),
        )

        missing.forEach(async (entry) => {
          try {
            const { envelope: env, sessionId: sid } = await loadExport(entry.filename)
            upsertLibraryEntry({
              sessionId: sid,
              runId: (env as any).run_id ?? null,
              title: entry.title,
              deckType: entry.deck_type,
              status: 'completed',
              envelope: env,
              totalSlides: entry.total_slides,
              appendixSlides: entry.appendix_slides,
              createdAt: entry.saved_at,
              exportedAt: entry.saved_at,
            })
          } catch { /* skip unreadable files */ }
        })

        // Remove local entries whose remote file has been deleted
        library
          .filter((e) => e.exportedAt && !remoteIds.has(e.sessionId))
          .forEach((e) => removeFromLibrary(e.sessionId))
      })
      .catch(() => { /* offline or no exports yet — fine */ })
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const handleLoadEntry = async (entry: DeckLibraryEntry) => {
    if (entry.sessionId === sessionId) return  // already active
    setLoadingFile(entry.sessionId)
    try {
      // Try to (re-)register the session on the backend so Export works
      const { restoreSession } = await import('@/api/client')
      const restored = await restoreSession({
        session_id: entry.sessionId,
        ...JSON.parse(JSON.stringify(entry.envelope)),
      })
      switchToDeck({ ...entry, sessionId: restored.session_id })
    } catch {
      // Backend unreachable — switch locally anyway (approve_and_export will recover)
      switchToDeck(entry)
    } finally {
      setLoadingFile(null)
    }
  }

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) }
    catch { return iso }
  }

  // ── Layout ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-full overflow-hidden">

      {/* ── LEFT: Deck library ──────────────────────────────────────────── */}
      <div className="w-72 shrink-0 border-r border-gray-200 flex flex-col bg-gray-50 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-white flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            My Decks
            {library.length > 0 && (
              <span className="ml-1.5 text-xs text-gray-400 font-normal">({library.length})</span>
            )}
          </h2>
          <button
            onClick={() => setTab('intake')}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
            title="Generate a new deck"
          >
            + New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {/* In-progress deck at top (not yet in library) */}
          {isRunning && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2.5">
              <p className="text-xs font-semibold text-yellow-700 truncate">Generating…</p>
              <AgentStatusBadge
                status={status}
                stage={currentStage}
                progressPct={progressPct}
                error={error}
                compact
              />
            </div>
          )}

          {/* Library entries */}
          {library.length === 0 && !isRunning ? (
            <div className="text-center py-10 px-4">
              <p className="text-xs text-gray-400">No decks yet.</p>
              <button
                onClick={() => setTab('intake')}
                className="mt-2 text-xs text-brand-600 underline hover:no-underline"
              >
                Generate your first deck →
              </button>
            </div>
          ) : (
            library.map((entry) => {
              const isActive = entry.sessionId === sessionId
              const isLoading = loadingFile === entry.sessionId
              return (
                <button
                  key={entry.sessionId}
                  onClick={() => handleLoadEntry(entry)}
                  disabled={isLoading}
                  className={[
                    'w-full text-left rounded-lg px-3 py-2.5 transition-colors border',
                    isActive
                      ? 'bg-brand-50 border-brand-300 shadow-sm'
                      : 'bg-white border-gray-200 hover:border-brand-200 hover:bg-brand-50/40',
                  ].join(' ')}
                >
                  {/* Run ID badge */}
                  {entry.runId && (
                    <span className={`text-[10px] font-mono font-bold tracking-wide ${isActive ? 'text-brand-500' : 'text-gray-400'}`}>
                      {entry.runId}
                    </span>
                  )}
                  <p className={`text-xs font-semibold truncate leading-snug ${isActive ? 'text-brand-700' : 'text-gray-800'}`}>
                    {isLoading ? '⏳ Loading…' : entry.title}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {entry.deckType && (
                      <span className="text-[10px] text-gray-400">{entry.deckType}</span>
                    )}
                    <span className="text-[10px] text-gray-300">·</span>
                    <span className="text-[10px] text-gray-400">
                      {entry.totalSlides}+{entry.appendixSlides} slides
                    </span>
                    {entry.exportedAt && (
                      <>
                        <span className="text-[10px] text-gray-300">·</span>
                        <span className="text-[10px] text-green-600">✓ exported</span>
                      </>
                    )}
                  </div>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    {formatDate(entry.createdAt)}
                  </p>
                </button>
              )
            })
          )}
        </div>
      </div>

      {/* ── RIGHT: Active deck ───────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex overflow-hidden">
        {/* No active deck */}
        {!isComplete || !envelope ? (
          <div className="flex-1 flex items-center justify-center text-center px-8">
            <div>
              <div className="text-4xl mb-3">🗂️</div>
              <p className="text-sm font-semibold text-gray-600 mb-1">
                {library.length > 0 ? 'Select a deck from the sidebar' : 'No decks yet'}
              </p>
              <p className="text-xs text-gray-400">
                {library.length > 0
                  ? 'Click any deck on the left to review it.'
                  : 'Go to the Intake tab to generate your first deck.'}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-1 min-w-0 overflow-hidden">
            {/* Slide list */}
            <div className="w-80 shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50">
              {deck && (
                <div className="px-4 py-3 border-b border-gray-200 bg-white sticky top-0 z-10">
                  <h2 className="font-bold text-gray-900 text-sm leading-snug">{deck.title}</h2>
                  <div className="flex gap-1.5 mt-1.5 flex-wrap">
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{deck.type}</span>
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{deck.total_slides} slides</span>
                  </div>
                  <button
                    onClick={approve_and_export}
                    className="mt-2.5 w-full py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors"
                  >
                    ✓ Approve &amp; Export
                  </button>
                </div>
              )}
              <div className="p-3 space-y-3">
                {slides.map((slide) => (
                  <SlideCard key={slide.slide_id} slide={slide} />
                ))}
                <AppendixSection />
              </div>
            </div>

            {/* Editor */}
            <div className="flex-1 min-w-0 overflow-hidden">
              {selectedSlideId ? (
                <SlideEditor />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                  <div className="text-center">
                    <div className="text-3xl mb-2">←</div>
                    <p>Select a slide to edit</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
