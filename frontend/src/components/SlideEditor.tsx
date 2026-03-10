/**
 * SlideEditor — right-panel editor for the selected slide.
 * Composes the 4 sub-editors + speaker notes toggle.
 */
import { useStore, useSelectedSlide } from '@/store'
import { useDeck } from '@/hooks/useDeck'
import TitleEditor from '@/components/editors/TitleEditor'
import MetaphorEditor from '@/components/editors/MetaphorEditor'
import KeyPointsEditor from '@/components/editors/KeyPointsEditor'
import EvidenceEditor from '@/components/editors/EvidenceEditor'

export default function SlideEditor() {
  const { showSpeakerNotes, toggleSpeakerNotes, status } = useStore((s) => ({
    showSpeakerNotes: s.showSpeakerNotes,
    toggleSpeakerNotes: s.toggleSpeakerNotes,
    status: s.status,
  }))
  const slide = useSelectedSlide()
  const { editSlide } = useDeck()

  const isComplete = status === 'completed' || status === 'complete'
  const disabled = !isComplete

  if (!slide) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm p-8 text-center">
        <div>
          <div className="text-3xl mb-3">🖱️</div>
          <p>Select a slide from the gallery to edit it</p>
        </div>
      </div>
    )
  }

  const save = (field: string) => async (value: unknown) => {
    await editSlide(slide.slide_id, field, value)
  }

  return (
    <div className="h-full overflow-y-auto p-5 space-y-6">
      {/* Slide ID + section */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono font-semibold text-gray-400">
          Slide {slide.slide_id}
        </span>
        <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
          {slide.section}
        </span>
      </div>

      {/* Title */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Title</h3>
        <TitleEditor
          value={slide.title}
          onSave={save('title')}
          disabled={disabled}
        />
      </section>

      {/* Objective */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Objective</h3>
        <p className="text-sm text-gray-600 italic">{slide.objective}</p>
      </section>

      {/* Metaphor */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Metaphor <span className="text-red-400 text-xs normal-case">(exactly 1 sentence)</span>
        </h3>
        <MetaphorEditor
          value={slide.metaphor}
          onSave={save('metaphor')}
          disabled={disabled}
        />
      </section>

      {/* Key points */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Key Points <span className="text-gray-400 text-xs normal-case">(max 5)</span>
        </h3>
        <KeyPointsEditor
          value={slide.key_points}
          onSave={save('key_points')}
          disabled={disabled}
        />
      </section>

      {/* Evidence */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Evidence <span className="text-gray-400 text-xs normal-case">(max 3)</span>
        </h3>
        <EvidenceEditor
          value={slide.evidence}
          onSave={save('evidence')}
          disabled={disabled}
        />
      </section>

      {/* Takeaway */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Takeaway</h3>
        <p className="text-sm text-gray-700 font-medium">{slide.takeaway}</p>
      </section>

      {/* Visual */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Visual</h3>
        <div className="text-xs text-gray-500 space-y-1">
          <p>
            <span className="font-semibold">Layout:</span> {slide.visual.layout}
          </p>
          <p>
            <span className="font-semibold">Type:</span> {slide.visual.illustration_prompt.type}
          </p>
          <p className="text-gray-600 italic">{slide.visual.illustration_prompt.description}</p>
        </div>
      </section>

      {/* Speaker notes */}
      <section>
        <button
          onClick={toggleSpeakerNotes}
          className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5 hover:text-gray-700"
        >
          <span>{showSpeakerNotes ? '▼' : '▶'}</span>
          Speaker Notes
        </button>
        {showSpeakerNotes && slide.speaker_notes && (
          <p className="mt-2 text-sm text-gray-600 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 whitespace-pre-wrap">
            {slide.speaker_notes}
          </p>
        )}
        {showSpeakerNotes && !slide.speaker_notes && (
          <p className="mt-2 text-xs text-gray-400 italic">No speaker notes for this slide.</p>
        )}
      </section>
    </div>
  )
}
