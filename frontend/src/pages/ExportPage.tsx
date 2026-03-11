/**
 * ExportPage — Tab 3: Export, download, and version history.
 * Shows JSON preview, export result, and version list.
 */
import { useState, useEffect } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { useDeck } from '@/hooks/useDeck'
import { getDeckHistory } from '@/api/client'
import JsonPreview from '@/components/JsonPreview'

interface VersionEntry {
  filename: string
  version: number
  saved_at: string
  size_bytes: number
}

export default function ExportPage() {
  const { envelope, exportResult, sessionId, error, runId } = useStore(useShallow((s) => ({
    envelope: s.envelope,
    exportResult: s.exportResult,
    sessionId: s.sessionId,
    error: s.error,
    runId: s.runId,
  })))
  const { approve_and_export } = useDeck()
  const [versions, setVersions] = useState<VersionEntry[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [exporting, setExporting] = useState(false)

  // Load version history when we have a session
  useEffect(() => {
    if (!sessionId) return
    setLoadingHistory(true)
    getDeckHistory(sessionId)
      .then((res) => setVersions(res.versions ?? []))
      .catch(() => setVersions([]))
      .finally(() => setLoadingHistory(false))
  }, [sessionId, exportResult])

  const handleExport = async () => {
    setExporting(true)
    await approve_and_export()
    setExporting(false)
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  // No deck yet
  if (!envelope?.deck) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <div className="text-5xl mb-4">📤</div>
        <h2 className="text-lg font-semibold text-gray-700 mb-2">Nothing to export yet</h2>
        <p className="text-sm text-gray-500">
          Complete the deck generation and review it in the Gallery tab first.
        </p>
      </div>
    )
  }

  const deck = envelope.deck

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {/* ── Deck summary ── */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            {runId && (
              <div className="inline-flex items-center gap-1.5 mb-2 px-2.5 py-1 rounded-lg bg-brand-50 border border-brand-200">
                <span className="text-xs text-brand-500">Run</span>
                <span className="text-xs font-bold text-brand-700 font-mono tracking-wide">{runId}</span>
              </div>
            )}
            <h2 className="font-bold text-gray-900 text-lg">{deck.title}</h2>
            <div className="flex gap-2 mt-2 flex-wrap">
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{deck.type}</span>
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{deck.total_slides} main slides</span>
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">
                {deck.appendix.slides.length} appendix slides
              </span>
              <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{deck.audience}</span>
            </div>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="shrink-0 px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {exporting ? (
              <><span className="animate-spin">⏳</span> Exporting…</>
            ) : (
              '📥 Approve & Export JSON'
            )}
          </button>
        </div>

        {/* Export error */}
        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-3">
            <span className="text-xl">❌</span>
            <div>
              <p className="text-sm font-semibold text-red-800">Export failed</p>
              <p className="text-xs text-red-700 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Export result */}
        {exportResult && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-xl px-4 py-3 flex items-start gap-3">
            <span className="text-xl">✅</span>
            <div>
              <p className="text-sm font-semibold text-green-800">Export successful</p>
              <p className="text-xs text-green-700 font-mono mt-0.5">{exportResult.filename}</p>
              <p className="text-xs text-green-600 mt-0.5">
                v{exportResult.version} · {formatBytes(exportResult.size_bytes)} · {formatDate(exportResult.saved_at)}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── JSON Preview ── */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <span>{'{ }'}</span> Deck JSON Preview
          <span className="text-xs text-gray-400 font-normal">
            ({deck.slides.length + deck.appendix.slides.length} slides)
          </span>
        </h3>
        <JsonPreview data={envelope} />
      </div>

      {/* ── Version history ── */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          🗂️ Export History
        </h3>
        {loadingHistory ? (
          <p className="text-sm text-gray-400">Loading history…</p>
        ) : versions.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No exports yet for this session.</p>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100 shadow-sm overflow-hidden">
            {versions.map((v, i) => (
              <div key={i} className="px-4 py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs font-mono font-semibold text-brand-600 shrink-0">
                    v{v.version}
                  </span>
                  <span className="text-xs font-mono text-gray-600 truncate">{v.filename}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                  <span>{formatBytes(v.size_bytes)}</span>
                  <span>{formatDate(v.saved_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Deck stats ── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Main Slides', value: deck.slides.length },
          { label: 'Appendix Slides', value: deck.appendix.slides.length },
          {
            label: 'Evidence Items',
            value: deck.slides.reduce((n, s) => n + s.evidence.length, 0),
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-xl border border-gray-200 p-4 text-center shadow-sm"
          >
            <p className="text-2xl font-bold text-brand-600">{stat.value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
