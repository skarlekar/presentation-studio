/**
 * SlideCard — displays a single slide in the gallery view.
 * Clicking selects the slide for editing.
 */
import clsx from 'clsx'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import type { Slide } from '@/types'

interface Props {
  slide: Slide
  isAppendix?: boolean
}

const SECTION_COLORS: Record<string, string> = {
  Setup: 'border-l-blue-400',
  Insight: 'border-l-purple-400',
  Resolution: 'border-l-green-400',
  Appendix: 'border-l-gray-300',
}

export default function SlideCard({ slide, isAppendix = false }: Props) {
  const { selectedSlideId, selectSlide } = useStore(useShallow((s) => ({
    selectedSlideId: s.selectedSlideId,
    selectSlide: s.selectSlide,
  })))

  const isSelected = selectedSlideId === slide.slide_id
  const sectionColor = SECTION_COLORS[slide.section] ?? 'border-l-gray-200'

  return (
    <button
      onClick={() => selectSlide(isSelected ? null : slide.slide_id)}
      className={clsx(
        'w-full text-left bg-white border border-gray-200 rounded-xl p-4 border-l-4 transition-all',
        sectionColor,
        isSelected
          ? 'ring-2 ring-brand-500 shadow-md'
          : 'hover:shadow-sm hover:border-gray-300',
        isAppendix && 'opacity-90',
      )}
      aria-pressed={isSelected}
      aria-label={`Slide ${slide.slide_id}: ${slide.title}`}
    >
      {/* Slide header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs font-mono font-semibold text-gray-400 shrink-0">
          {slide.slide_id}
        </span>
        <span className="text-xs text-gray-400 shrink-0">{slide.section}</span>
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-gray-900 leading-snug mb-2">
        {slide.title}
      </h3>

      {/* Key points — all of them, fully visible */}
      {slide.key_points.length > 0 && (
        <ul className="text-xs text-gray-600 space-y-1 mb-2">
          {slide.key_points.map((pt, i) => (
            <li key={i} className="flex gap-1.5 items-start">
              <span className="mt-0.5 text-gray-300 shrink-0">•</span>
              <span>{pt}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Takeaway */}
      {slide.takeaway && (
        <p className="text-xs font-medium text-gray-700 border-t border-gray-100 pt-2 mt-2">
          🎯 {slide.takeaway}
        </p>
      )}

      {/* Metaphor */}
      {slide.metaphor && (
        <p className="text-xs text-indigo-600 italic border-t border-gray-100 pt-2 mt-2">
          💡 {slide.metaphor}
        </p>
      )}

      {/* Evidence badge */}
      {slide.evidence.length > 0 && (
        <div className="flex gap-1 mt-2 flex-wrap">
          {slide.evidence.map((ev, i) => (
            <span
              key={i}
              className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-mono"
            >
              {ev.type}
            </span>
          ))}
        </div>
      )}
    </button>
  )
}
