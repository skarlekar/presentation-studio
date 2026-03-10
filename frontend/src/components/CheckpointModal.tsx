/**
 * CheckpointModal — HITL gate modal shown when the pipeline pauses for human review.
 * Allows viewing the pending stage output, optionally editing, then approving or rejecting.
 */
import { useState } from 'react'
import { useStore } from '@/store'
import { useDeck } from '@/hooks/useDeck'

export default function CheckpointModal() {
  const { checkpoint, closeCheckpointModal } = useStore((s) => ({
    checkpoint: s.checkpoint,
    closeCheckpointModal: s.closeCheckpointModal,
  }))
  const { approve, reject } = useDeck()

  const [feedback, setFeedback] = useState('')
  const [mode, setMode] = useState<'review' | 'reject'>('review')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!checkpoint) return null

  const preview = checkpoint.preview ?? checkpoint.pending_input ?? {}

  const handleApprove = async () => {
    setIsSubmitting(true)
    await approve()
    setIsSubmitting(false)
  }

  const handleReject = async () => {
    if (!feedback.trim() || feedback.trim().length < 10) return
    setIsSubmitting(true)
    await reject(feedback.trim())
    setIsSubmitting(false)
    setFeedback('')
    setMode('review')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="checkpoint-title"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-0.5">
              Human-in-the-loop checkpoint
            </p>
            <h2 id="checkpoint-title" className="text-lg font-bold text-gray-900">
              {checkpoint.label || 'Review Required'}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Stage {checkpoint.stage_index || '?'} of 5 —{' '}
              {checkpoint.stage?.replace(/_/g, ' ') || 'Unknown stage'}
            </p>
          </div>
          <span className="text-2xl mt-0.5">👁️</span>
        </div>

        {/* Body — preview content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {mode === 'review' ? (
            <>
              <p className="text-sm text-gray-600">
                The AI has completed this stage. Review the output below and approve to continue,
                or reject with specific revision instructions.
              </p>

              <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-100 flex items-center gap-2">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Stage output preview
                  </span>
                </div>
                <pre className="px-4 py-4 text-xs text-gray-700 overflow-auto max-h-64 whitespace-pre-wrap">
                  {JSON.stringify(preview, null, 2)}
                </pre>
              </div>
            </>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-700 font-medium">
                Provide revision instructions for the AI agent:
              </p>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Be specific — e.g. 'The slide titles are topic labels, not conclusion statements. Rewrite them to lead with the insight.'"
                rows={6}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                aria-label="Rejection feedback"
              />
              <p className="text-xs text-gray-400">
                {feedback.trim().length}/10 characters minimum
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex justify-between gap-3">
          {mode === 'review' ? (
            <>
              <button
                onClick={() => setMode('reject')}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                ✗ Reject &amp; Revise
              </button>
              <button
                onClick={handleApprove}
                disabled={isSubmitting}
                className="px-6 py-2 text-sm font-semibold bg-brand-600 text-white rounded-xl hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <span className="animate-spin">⏳</span> Resuming…
                  </>
                ) : (
                  '✓ Approve & Continue'
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setMode('review')}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                ← Back
              </button>
              <button
                onClick={handleReject}
                disabled={isSubmitting || feedback.trim().length < 10}
                className="px-6 py-2 text-sm font-semibold bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <span className="animate-spin">⏳</span> Submitting…
                  </>
                ) : (
                  '✗ Submit Rejection'
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
