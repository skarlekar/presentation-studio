/**
 * AgentStatusBadge — shows current pipeline status + stage with animated indicator.
 */
import clsx from 'clsx'
import type { PipelineStatus } from '@/types'

interface Props {
  status: PipelineStatus | null
  stage?: string | null
  progressPct?: number
  error?: string | null
  compact?: boolean   // reduced footprint for sidebar use
}

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; animate: boolean; icon: string }
> = {
  pending: { label: 'Pending', color: 'bg-gray-100 text-gray-600', animate: false, icon: '⏳' },
  running: { label: 'Running', color: 'bg-blue-100 text-blue-700', animate: true, icon: '🔄' },
  extracting_insights: { label: 'Extracting Insights', color: 'bg-blue-100 text-blue-700', animate: true, icon: '🔍' },
  generating_outline: { label: 'Designing Outline', color: 'bg-blue-100 text-blue-700', animate: true, icon: '🗂️' },
  awaiting_approval: { label: 'Awaiting Your Review', color: 'bg-amber-100 text-amber-700', animate: false, icon: '👁️' },
  awaiting_outline_approval: { label: 'Awaiting Outline Review', color: 'bg-amber-100 text-amber-700', animate: false, icon: '📋' },
  generating_slides: { label: 'Generating Slides', color: 'bg-blue-100 text-blue-700', animate: true, icon: '✍️' },
  awaiting_review_approval: { label: 'Awaiting Slide Review', color: 'bg-amber-100 text-amber-700', animate: false, icon: '🔎' },
  validating: { label: 'Validating', color: 'bg-purple-100 text-purple-700', animate: true, icon: '✅' },
  complete: { label: 'Complete', color: 'bg-green-100 text-green-700', animate: false, icon: '🎉' },
  completed: { label: 'Complete', color: 'bg-green-100 text-green-700', animate: false, icon: '🎉' },
  failed: { label: 'Failed', color: 'bg-red-100 text-red-700', animate: false, icon: '❌' },
  rejected: { label: 'Rejected', color: 'bg-orange-100 text-orange-700', animate: false, icon: '🚫' },
  cancelled: { label: 'Cancelled', color: 'bg-gray-100 text-gray-500', animate: false, icon: '⛔' },
}

const STAGE_LABELS: Record<string, string> = {
  insight_extractor: 'Stage 1/5 — Extracting Insights',
  deck_architect: 'Stage 2/5 — Designing Structure',
  slide_generator: 'Stage 3/5 — Generating Slides',
  appendix_builder: 'Stage 4/5 — Building Appendix',
  quality_validator: 'Stage 5/5 — Validating Quality',
}

export default function AgentStatusBadge({ status, stage, progressPct, error }: Props) {
  if (!status) return null

  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG['pending']
  const stageLabel = stage ? (STAGE_LABELS[stage] ?? stage.replace(/_/g, ' ')) : null

  return (
    <div className="space-y-2">
      <div className={clsx('inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium', cfg.color)}>
        <span
          className={clsx('text-base', cfg.animate && 'animate-spin')}
          aria-hidden="true"
        >
          {cfg.icon}
        </span>
        <span>{cfg.label}</span>
        {stageLabel && (
          <span className="opacity-60 text-xs">— {stageLabel}</span>
        )}
      </div>

      {/* Progress bar */}
      {progressPct !== undefined && progressPct > 0 && progressPct < 100 && (
        <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-brand-600 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
            role="progressbar"
            aria-valuenow={progressPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      )}

      {/* Error detail */}
      {error && (
        <p className="text-sm text-red-600 mt-1">{error}</p>
      )}
    </div>
  )
}
