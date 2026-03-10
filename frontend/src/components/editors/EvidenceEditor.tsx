/**
 * EvidenceEditor — editable list for slide evidence items (max 3).
 */
import { useState } from 'react'
import type { EvidenceItem, EvidenceType } from '@/types'

interface Props {
  value: EvidenceItem[]
  onSave: (newValue: EvidenceItem[]) => Promise<void>
  disabled?: boolean
}

const MAX_EVIDENCE = 3

const EVIDENCE_TYPES: EvidenceType[] = [
  'metric', 'reference', 'benchmark', 'case_study', 'quote',
]

const TYPE_COLORS: Record<EvidenceType, string> = {
  metric: 'bg-blue-100 text-blue-700',
  reference: 'bg-purple-100 text-purple-700',
  benchmark: 'bg-orange-100 text-orange-700',
  case_study: 'bg-green-100 text-green-700',
  quote: 'bg-pink-100 text-pink-700',
}

const EMPTY_EVIDENCE: EvidenceItem = { type: 'metric', detail: '', source: '' }

export default function EvidenceEditor({ value, onSave, disabled }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<EvidenceItem[]>([...value])
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    const cleaned = draft.filter((e) => e.detail.trim().length > 0)
    setSaving(true)
    await onSave(cleaned)
    setSaving(false)
    setEditing(false)
  }

  const addEvidence = () => {
    if (draft.length < MAX_EVIDENCE) {
      setDraft([...draft, { ...EMPTY_EVIDENCE }])
    }
  }

  const removeEvidence = (idx: number) => setDraft(draft.filter((_, i) => i !== idx))

  const updateEvidence = (idx: number, field: keyof EvidenceItem, val: string) => {
    const next = [...draft]
    next[idx] = { ...next[idx], [field]: val }
    setDraft(next)
  }

  if (!editing) {
    return (
      <div className="group relative">
        <div className="space-y-2">
          {value.map((ev, i) => (
            <div key={i} className="flex gap-2 items-start">
              <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${TYPE_COLORS[ev.type]}`}>
                {ev.type}
              </span>
              <div>
                <p className="text-sm text-gray-700">{ev.detail}</p>
                {ev.source && <p className="text-xs text-gray-400">{ev.source}</p>}
              </div>
            </div>
          ))}
          {value.length === 0 && <p className="text-xs text-gray-400 italic">No evidence items</p>}
        </div>
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
          Evidence <span className="text-gray-400">({draft.length}/{MAX_EVIDENCE} max)</span>
        </label>
        {draft.length < MAX_EVIDENCE && (
          <button
            onClick={addEvidence}
            className="text-xs text-brand-600 hover:text-brand-700"
          >
            + Add evidence
          </button>
        )}
      </div>

      {draft.map((ev, i) => (
        <div key={i} className="border border-gray-200 rounded-xl p-3 space-y-2">
          <div className="flex gap-2 items-center">
            <select
              value={ev.type}
              onChange={(e) => updateEvidence(i, 'type', e.target.value)}
              className="text-xs border border-gray-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand-500"
              disabled={saving}
            >
              {EVIDENCE_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button
              onClick={() => removeEvidence(i)}
              className="ml-auto text-gray-400 hover:text-red-500 text-xs"
              aria-label={`Remove evidence ${i + 1}`}
            >
              Remove
            </button>
          </div>
          <input
            type="text"
            value={ev.detail}
            onChange={(e) => updateEvidence(i, 'detail', e.target.value)}
            placeholder="Evidence detail (required)"
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            disabled={saving}
          />
          <input
            type="text"
            value={ev.source ?? ''}
            onChange={(e) => updateEvidence(i, 'source', e.target.value)}
            placeholder="Source citation (optional)"
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-xs text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
            disabled={saving}
          />
        </div>
      ))}

      {draft.length === 0 && (
        <p className="text-xs text-gray-400 italic text-center py-2">
          No evidence — click "+ Add evidence"
        </p>
      )}

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
