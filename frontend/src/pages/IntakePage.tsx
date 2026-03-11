/**
 * IntakePage — Tab 1: The deck generation intake form.
 * Collects all DeckRequest fields and starts the pipeline.
 */
import { useState, useCallback } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { useDeck } from '@/hooks/useDeck'
import AgentStatusBadge from '@/components/AgentStatusBadge'
import PipelineProgress from '@/components/PipelineProgress'
import { fetchUrl, ApiError } from '@/api/client'
import type { DeckRequest, DeckType, DecisionInformAsk } from '@/types'

const DECK_TYPES: DeckType[] = [
  'Decision Deck',
  'Strategy Deck',
  'Update Deck',
  'Technical Deep Dive',
  'Pitch Deck',
]

const DIA_OPTIONS: DecisionInformAsk[] = ['Decision', 'Inform', 'Ask']

const DEFAULT_FORM: DeckRequest = {
  context: '',
  number_of_slides: 5,
  audience: '',
  deck_type: 'Decision Deck',
  decision_inform_ask: 'Decision',
  tone: 'Authoritative, data-driven, executive-grade',
  source_material: '',
  must_include_sections: [],
  top_messages: [],
}

export default function IntakePage() {
  const [form, setForm] = useState<DeckRequest>(DEFAULT_FORM)
  const [mustInclude, setMustInclude] = useState('')
  const [topMsg, setTopMsg] = useState('')

  // URL fetcher state
  const [urlInput, setUrlInput] = useState('')
  const [urlFetching, setUrlFetching] = useState(false)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [urlSuccess, setUrlSuccess] = useState<string | null>(null)

  const { status, progressPct, currentStage, error, isPolling } = useStore(useShallow((s) => ({
    status: s.status,
    progressPct: s.progressPct,
    currentStage: s.currentStage,
    error: s.error,
    isPolling: s.isPolling,
  })))
  const { startGeneration, reset } = useDeck()
  const runId = useStore(s => s.runId)

  const isRunning = isPolling || status === 'running' || status === 'awaiting_approval'
  const isComplete = status === 'completed' || status === 'complete'
  const isFailed = status === 'failed' || status === 'rejected'

  const set = useCallback(
    <K extends keyof DeckRequest>(key: K, value: DeckRequest[K]) => {
      setForm((f) => ({ ...f, [key]: value }))
    },
    [],
  )

  const handleFetchUrl = async () => {
    const url = urlInput.trim()
    if (!url) return
    setUrlFetching(true)
    setUrlError(null)
    setUrlSuccess(null)
    try {
      const result = await fetchUrl(url)
      // Append fetched content to existing source material (don't clobber)
      const existing = (form.source_material ?? '').trim()
      const separator = existing ? '\n\n---\n\n' : ''
      const header = result.title ? `Source: ${result.title}\nURL: ${url}\n\n` : `Source URL: ${url}\n\n`
      set('source_material', existing + separator + header + result.content)
      setUrlSuccess(`Fetched ${result.char_count.toLocaleString()} characters${result.title ? ` from "${result.title}"` : ''}`)
      setUrlInput('')
    } catch (err) {
      setUrlError(err instanceof ApiError ? err.detail : 'Failed to fetch URL')
    } finally {
      setUrlFetching(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const req: DeckRequest = {
      ...form,
      context: form.context || null,
      source_material: form.source_material || null,
      must_include_sections: mustInclude
        ? mustInclude.split('\n').map((s) => s.trim()).filter(Boolean)
        : null,
      top_messages: topMsg
        ? topMsg.split('\n').map((s) => s.trim()).filter(Boolean)
        : null,
    }
    await startGeneration(req)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Status banner */}
      {status && (
        <div className="mb-6">
          {isRunning ? (
            <div className="space-y-3">
              <AgentStatusBadge
                status={status}
                stage={currentStage}
                progressPct={progressPct}
                error={error}
              />
              <PipelineProgress />
            </div>
          ) : (
            <AgentStatusBadge
              status={status}
              stage={currentStage}
              progressPct={progressPct}
              error={error}
            />
          )}
          {isComplete && (
            <div className="mt-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-green-700 font-medium">
                  ✓ Deck complete — view it in the <strong>Gallery</strong> tab.
                </p>
                {runId && (
                  <p className="text-xs text-green-600 font-mono mt-0.5">Run ID: {runId}</p>
                )}
              </div>
              <button
                type="button"
                onClick={reset}
                className="shrink-0 text-xs font-semibold text-green-700 underline hover:no-underline"
              >
                Start New Deck
              </button>
            </div>
          )}
          {isFailed && (
            <button
              onClick={reset}
              className="mt-3 text-sm text-brand-600 underline hover:no-underline"
            >
              Start over
            </button>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-5 shadow-sm">
          <h2 className="text-base font-bold text-gray-900">Deck Configuration</h2>

          {/* Context */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              Context <span className="text-red-400">*</span>
            </label>
            <textarea
              value={form.context ?? ''}
              onChange={(e) => set('context', e.target.value)}
              rows={4}
              placeholder="Background, situation, purpose, and framing for the deck. What problem are you solving? What decisions need to be made?"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              required={!form.source_material}
            />
          </div>

          {/* Source material */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              Source Material
              <span className="text-gray-400 font-normal ml-2">(optional — paste research, reports, data)</span>
            </label>

            {/* URL Fetcher */}
            <div className="mb-2">
              <div className="flex gap-2">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => { setUrlInput(e.target.value); setUrlError(null); setUrlSuccess(null) }}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleFetchUrl() } }}
                  placeholder="Paste a URL to fetch content automatically (Medium, LinkedIn, blogs…)"
                  className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  disabled={urlFetching}
                />
                <button
                  type="button"
                  onClick={handleFetchUrl}
                  disabled={urlFetching || !urlInput.trim()}
                  className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl disabled:opacity-40 transition-colors whitespace-nowrap flex items-center gap-1.5"
                >
                  {urlFetching ? (
                    <><span className="animate-spin text-base">⏳</span> Fetching…</>
                  ) : (
                    <><span>🔗</span> Fetch URL</>
                  )}
                </button>
              </div>
              {urlError && (
                <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
                  <span>⚠️</span> {urlError}
                </p>
              )}
              {urlSuccess && (
                <p className="mt-1.5 text-xs text-green-700 flex items-center gap-1">
                  <span>✓</span> {urlSuccess}
                </p>
              )}
            </div>

            <textarea
              value={form.source_material ?? ''}
              onChange={(e) => set('source_material', e.target.value)}
              rows={6}
              placeholder="Paste documents, research, data, or transcripts here — or use the URL fetcher above."
              className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
            {form.source_material && (
              <p className="mt-1 text-xs text-gray-400 text-right">
                {(form.source_material ?? '').length.toLocaleString()} characters
              </p>
            )}
          </div>

          {/* Row: deck type + DIA */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Deck Type <span className="text-red-400">*</span>
              </label>
              <select
                value={form.deck_type}
                onChange={(e) => set('deck_type', e.target.value as DeckType)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              >
                {DECK_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Decision / Inform / Ask <span className="text-red-400">*</span>
              </label>
              <select
                value={form.decision_inform_ask}
                onChange={(e) => set('decision_inform_ask', e.target.value as DecisionInformAsk)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              >
                {DIA_OPTIONS.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Audience */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              Audience <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.audience}
              onChange={(e) => set('audience', e.target.value)}
              placeholder="e.g. C-suite executives at a Fortune 500 financial services firm"
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>

          {/* Tone */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              Tone <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.tone}
              onChange={(e) => set('tone', e.target.value)}
              placeholder="e.g. Authoritative and data-driven"
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>

          {/* Slide count */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1.5">
              Number of Slides <span className="text-gray-400 font-normal">(3–60)</span>
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={3}
                max={60}
                value={form.number_of_slides}
                onChange={(e) => set('number_of_slides', Number(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm font-semibold text-brand-600 w-8 text-center">
                {form.number_of_slides}
              </span>
            </div>
          </div>
        </div>

        {/* Optional fields */}
        <details className="bg-white rounded-2xl border border-gray-200 shadow-sm">
          <summary className="px-6 py-4 text-sm font-semibold text-gray-700 cursor-pointer select-none">
            Optional fields ▸ Must-include sections, top messages
          </summary>
          <div className="px-6 pb-5 space-y-4 border-t border-gray-100 pt-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Must-Include Sections <span className="text-gray-400 font-normal">(one per line)</span>
              </label>
              <textarea
                value={mustInclude}
                onChange={(e) => setMustInclude(e.target.value)}
                rows={3}
                placeholder="Executive Summary&#10;Risk &amp; Mitigations&#10;Decision / CTA"
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                Top Messages <span className="text-gray-400 font-normal">(one per line, max 5)</span>
              </label>
              <textarea
                value={topMsg}
                onChange={(e) => setTopMsg(e.target.value)}
                rows={3}
                placeholder="Key message 1&#10;Key message 2"
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
            </div>
          </div>
        </details>

        {/* Submit */}
        <button
          type="submit"
          disabled={isRunning}
          className="w-full py-3.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
        >
          {isRunning ? (
            <>
              <span className="animate-spin">⏳</span>
              Generating deck…
            </>
          ) : isComplete ? (
            '🚀 Generate New Deck'
          ) : (
            '🚀 Generate Deck'
          )}
        </button>
      </form>
    </div>
  )
}
