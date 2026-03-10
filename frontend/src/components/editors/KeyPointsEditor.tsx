/**
 * KeyPointsEditor — editable list for slide key_points (max 5).
 */
import { useState } from 'react'

interface Props {
  value: string[]
  onSave: (newValue: string[]) => Promise<void>
  disabled?: boolean
}

const MAX_POINTS = 5

export default function KeyPointsEditor({ value, onSave, disabled }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<string[]>([...value])
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    const cleaned = draft.filter((p) => p.trim().length > 0)
    setSaving(true)
    await onSave(cleaned)
    setSaving(false)
    setEditing(false)
  }

  const addPoint = () => {
    if (draft.length < MAX_POINTS) setDraft([...draft, ''])
  }

  const removePoint = (idx: number) => {
    setDraft(draft.filter((_, i) => i !== idx))
  }

  const updatePoint = (idx: number, val: string) => {
    const next = [...draft]
    next[idx] = val
    setDraft(next)
  }

  if (!editing) {
    return (
      <div className="group relative">
        <ul className="text-sm text-gray-700 space-y-1">
          {value.map((pt, i) => (
            <li key={i} className="flex gap-2 items-start">
              <span className="text-brand-400 mt-0.5 shrink-0">•</span>
              <span>{pt}</span>
            </li>
          ))}
          {value.length === 0 && <li className="text-gray-400 italic text-xs">No key points</li>}
        </ul>
        {!disabled && (
          <button
            onClick={() => { setDraft([...value]); setEditing(true) }}
            className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 text-xs text-brand-600 bg-brand-50 px-2 py-0.5 rounded transition-opacity"
          >
            Edit
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
          Key Points <span className="text-gray-400">({draft.length}/{MAX_POINTS} max)</span>
        </label>
        {draft.length < MAX_POINTS && (
          <button
            onClick={addPoint}
            className="text-xs text-brand-600 hover:text-brand-700"
          >
            + Add point
          </button>
        )}
      </div>

      <div className="space-y-1.5">
        {draft.map((pt, i) => (
          <div key={i} className="flex gap-2 items-center">
            <input
              type="text"
              value={pt}
              onChange={(e) => updatePoint(i, e.target.value)}
              placeholder={`Point ${i + 1}`}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              disabled={saving}
            />
            <button
              onClick={() => removePoint(i)}
              className="text-gray-400 hover:text-red-500 text-sm px-1"
              aria-label={`Remove point ${i + 1}`}
            >
              ✕
            </button>
          </div>
        ))}
        {draft.length === 0 && (
          <p className="text-xs text-gray-400 italic">No key points — click "+ Add point"</p>
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs px-3 py-1 bg-brand-600 text-white rounded-lg disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={() => { setDraft([...value]); setEditing(false) }}
          disabled={saving}
          className="text-xs px-3 py-1 border border-gray-200 rounded-lg text-gray-500"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
