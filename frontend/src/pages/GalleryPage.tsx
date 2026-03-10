/**
 * GalleryPage — Tab 2: Slide gallery + right-panel editor.
 * Shows all main slides and appendix section; right panel opens on slide selection.
 */
import { useStore } from '@/store'
import { useDeck } from '@/hooks/useDeck'
import AgentStatusBadge from '@/components/AgentStatusBadge'
import SlideCard from '@/components/SlideCard'
import SlideEditor from '@/components/SlideEditor'
import AppendixSection from '@/components/AppendixSection'

export default function GalleryPage() {
  const { envelope, status, currentStage, progressPct, error, selectedSlideId } = useStore((s) => ({
    envelope: s.envelope,
    status: s.status,
    currentStage: s.currentStage,
    progressPct: s.progressPct,
    error: s.error,
    selectedSlideId: s.selectedSlideId,
  }))
  const { approve_and_export } = useDeck()

  const isComplete = status === 'completed' || status === 'complete'
  const slides = envelope?.deck?.slides ?? []
  const deck = envelope?.deck

  // Pipeline still running — show status
  if (!isComplete && !envelope) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <AgentStatusBadge
          status={status}
          stage={currentStage}
          progressPct={progressPct}
          error={error}
        />
        {!status && (
          <p className="text-gray-400 text-sm mt-4">
            Start a deck from the Intake tab to see slides here.
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* ── Left: slide list ── */}
      <div className="w-96 shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50">
        {/* Deck header */}
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

            {/* Approve & Export button */}
            <button
              onClick={approve_and_export}
              className="mt-3 w-full py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition-colors flex items-center justify-center gap-1.5"
            >
              ✓ Approve &amp; Export
            </button>
          </div>
        )}

        {/* Main slides */}
        <div className="p-4 space-y-3">
          {slides.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              No slides yet
            </div>
          ) : (
            <>
              {slides.map((slide) => (
                <SlideCard key={slide.slide_id} slide={slide} />
              ))}
              {/* Appendix */}
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
