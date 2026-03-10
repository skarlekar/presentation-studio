/**
 * MetaphorEditor — inline editor enforcing exactly-1-sentence constraint client-side.
 */
import { useState } from 'react'

interface Props {
  value: string
  onSave: (newValue: string) => Promise<void>
  disabled?: boolean
}

function countSentences(text: string): number {
  const parts = text.trim().split(/[.!?]+/).filter((s) => s.trim().length > 0)
  return parts.length
}

export default function MetaphorEditor({ value, onSave, disabled }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)

  const sentenceCount = countSentences(draft)
  const isValid = sentenceCount === 1

  const handleSave = async () => {
    if (!isValid) return
    if (draft.trim() === value) { setEditing(false); return }
    setSaving(true)
    await onSave(draft.trim())
    setSaving(false)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setDraft(value); setEditing(false) }
  }

  if (!editing) {
    return (
      <div className="group relative">
        <p className="text-sm text-indigo-700 italic">💡 {value}</p>
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
      <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
        Metaphor <span className="text-red-400">*</span>
      </label>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={2}
        autoFocus
        placeholder="Write a plain-language analogy that makes this slide's idea immediately clear."
        className={`w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 ${
          isValid ? 'border-green-400 focus:ring-green-500' : 'border-red-400 focus:ring-red-500'
        }`}
        aria-label="Metaphor"
        disabled={saving}
      />
      <div className="flex items-center justify-between text-xs">
        <span className={sentenceCount === 0 ? 'text-gray-400' : isValid ? 'text-green-600' : 'text-red-600'}>
          {sentenceCount === 0
            ? 'Write exactly 1 sentence'
            : isValid
            ? '✓ Exactly 1 sentence'
            : `✗ ${sentenceCount} sentences — must be exactly 1`}
        </span>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving || !isValid}
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
