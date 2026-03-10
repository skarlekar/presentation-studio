/**
 * TitleEditor — inline editor for slide title with conclusion-statement validation hint.
 */
import { useState } from 'react'

interface Props {
  value: string
  onSave: (newValue: string) => Promise<void>
  disabled?: boolean
}

export default function TitleEditor({ value, onSave, disabled }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (draft.trim() === value) { setEditing(false); return }
    setSaving(true)
    await onSave(draft.trim())
    setSaving(false)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') { setDraft(value); setEditing(false) }
  }

  if (!editing) {
    return (
      <div className="group relative">
        <h2 className="text-lg font-semibold text-gray-900 leading-snug">{value}</h2>
        {!disabled && (
          <button
            onClick={() => { setDraft(value); setEditing(true) }}
            className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 text-xs text-brand-600 bg-brand-50 px-2 py-0.5 rounded transition-opacity"
          >
            Edit
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
        className="w-full border border-brand-400 rounded-lg px-3 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500"
        aria-label="Slide title"
        disabled={saving}
      />
      <p className="text-xs text-amber-600">
        ⚠️ Title must be a conclusion statement with verb + outcome
        (e.g. "Event-driven ingestion reduces integration time by 40%")
      </p>
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || !draft.trim()}
          className="text-xs px-3 py-1 bg-brand-600 text-white rounded-lg disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={() => { setDraft(value); setEditing(false) }}
          disabled={saving}
          className="text-xs px-3 py-1 border border-gray-200 rounded-lg text-gray-500"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
