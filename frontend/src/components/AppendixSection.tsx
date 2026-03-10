/**
 * AppendixSection — collapsible appendix slide list in the gallery.
 */
import { useStore } from '@/store'
import SlideCard from '@/components/SlideCard'

export default function AppendixSection() {
  const { showAppendix, toggleAppendix, envelope } = useStore((s) => ({
    showAppendix: s.showAppendix,
    toggleAppendix: s.toggleAppendix,
    envelope: s.envelope,
  }))

  const appendixSlides = envelope?.deck?.appendix?.slides ?? []
  if (appendixSlides.length === 0) return null

  return (
    <section>
      <button
        onClick={toggleAppendix}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-100 rounded-xl border border-gray-200 hover:bg-gray-150 transition-colors"
        aria-expanded={showAppendix}
      >
        <div className="flex items-center gap-2">
          <span className="text-base">{showAppendix ? '▼' : '▶'}</span>
          <span className="font-semibold text-sm text-gray-700">
            Appendix
          </span>
          <span className="text-xs text-gray-400">
            {appendixSlides.length} slide{appendixSlides.length !== 1 ? 's' : ''}
          </span>
        </div>
        <span className="text-xs text-gray-400">Supporting data &amp; methodology</span>
      </button>

      {showAppendix && (
        <div className="mt-3 grid grid-cols-1 gap-3">
          {appendixSlides.map((slide) => (
            <SlideCard key={slide.slide_id} slide={slide} isAppendix />
          ))}
        </div>
      )}
    </section>
  )
}
