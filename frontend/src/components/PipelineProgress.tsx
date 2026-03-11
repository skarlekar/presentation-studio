/**
 * PipelineProgress — Visual pipeline diagram showing per-agent progress.
 *
 * Displays 5 agent nodes in a horizontal flow with arrows, status badges,
 * and click-to-view-output functionality.
 */
import { useStore } from '@/store'
import type { AgentStep } from '@/types'

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

interface AgentNodeConfig {
  name: string
  label: string
  icon: string
}

const PIPELINE_NODES: AgentNodeConfig[] = [
  { name: 'insight_extractor', label: 'Insight Extraction', icon: '🔍' },
  { name: 'deck_architect', label: 'Deck Architecture', icon: '🏗️' },
  { name: 'slide_generator', label: 'Slide Generation', icon: '📊' },
  { name: 'appendix_builder', label: 'Appendix Builder', icon: '📎' },
  { name: 'quality_validator', label: 'Quality Check', icon: '✅' },
]

function getStepStatus(steps: AgentStep[], name: string): AgentStep['status'] {
  const step = steps.find((s) => s.name === name)
  return step?.status ?? 'pending'
}

/** Returns true when quality_validator completed but found schema violations. */
function isValidationFailed(step: AgentStep | undefined): boolean {
  if (!step || step.status !== 'completed') return false
  const s = step.output_summary ?? ''
  return s.includes('violation') || s.includes('⚠️') || s.toLowerCase().includes('failed')
}

function getElapsedTime(step: AgentStep | undefined): string | null {
  if (!step?.started_at) return null
  const start = new Date(step.started_at).getTime()
  const end = step.completed_at ? new Date(step.completed_at).getTime() : Date.now()
  const seconds = Math.round((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs}s`
}

type VisualStatus = AgentStep['status'] | 'validation_failed' | 'regenerating'

const STATUS_STYLES: Record<VisualStatus, {
  border: string
  bg: string
  text: string
  pill: string
  pillText: string
  animate: boolean
}> = {
  pending: {
    border: 'border-gray-200',
    bg: 'bg-gray-50',
    text: 'text-gray-400',
    pill: 'bg-gray-100',
    pillText: 'text-gray-500',
    animate: false,
  },
  running: {
    border: 'border-blue-400',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    pill: 'bg-blue-100',
    pillText: 'text-blue-700',
    animate: true,
  },
  completed: {
    border: 'border-green-300',
    bg: 'bg-green-50',
    text: 'text-green-700',
    pill: 'bg-green-100',
    pillText: 'text-green-700',
    animate: false,
  },
  failed: {
    border: 'border-red-300',
    bg: 'bg-red-50',
    text: 'text-red-700',
    pill: 'bg-red-100',
    pillText: 'text-red-700',
    animate: false,
  },
  // Quality validator ran and found violations — pipeline will re-run slide_generator
  validation_failed: {
    border: 'border-orange-400',
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    pill: 'bg-orange-100',
    pillText: 'text-orange-700',
    animate: false,
  },
  // slide_generator is running again after a validation failure
  regenerating: {
    border: 'border-amber-400',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    pill: 'bg-amber-100',
    pillText: 'text-amber-700',
    animate: true,
  },
}

const PILL_LABELS: Record<VisualStatus, string> = {
  pending: 'Pending',
  running: 'Running…',
  completed: 'Done',
  failed: 'Failed',
  validation_failed: 'Violations Found',
  regenerating: 'Regenerating…',
}

export default function PipelineProgress() {
  const sessionId = useStore((s) => s.sessionId)
  const agentSteps = useStore((s) => s.agentSteps)

  const handleNodeClick = (name: string, status: AgentStep['status']) => {
    if (status !== 'completed' || !sessionId) return
    // Open agent output in a new tab (served as HTML by the backend)
    window.open(`${BASE_URL}/api/deck/${sessionId}/agents/${name}`, '_blank')
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
        <span className="font-semibold text-gray-700">Agent Pipeline</span>
        <span>
          {agentSteps.filter((s) => s.status === 'completed').length} / {PIPELINE_NODES.length} complete
        </span>
      </div>

      {/* Pipeline visualization */}
      <div className="flex items-stretch gap-1 overflow-x-auto pb-2">
        {PIPELINE_NODES.map((node, idx) => {
          const rawStatus = getStepStatus(agentSteps, node.name)
          const step = agentSteps.find((s) => s.name === node.name)
          const qvStep = agentSteps.find((s) => s.name === 'quality_validator')
          const inQualityLoop = isValidationFailed(qvStep)

          // Determine visual status — may differ from raw status during quality loop
          let visualStatus: VisualStatus = rawStatus
          if (node.name === 'quality_validator' && inQualityLoop) {
            visualStatus = 'validation_failed'
          } else if (node.name === 'slide_generator' && rawStatus === 'running' && inQualityLoop) {
            visualStatus = 'regenerating'
          }

          const style = STATUS_STYLES[visualStatus]
          const elapsed = getElapsedTime(step)
          const isClickable = rawStatus === 'completed'

          return (
            <div key={node.name} className="flex items-center">
              {/* Node card */}
              <button
                onClick={() => handleNodeClick(node.name, rawStatus)}
                disabled={!isClickable}
                className={`
                  relative flex flex-col items-center justify-between
                  w-[120px] min-h-[110px] px-3 py-3
                  border-2 rounded-xl transition-all duration-300
                  ${style.border} ${style.bg}
                  ${isClickable ? 'cursor-pointer hover:shadow-md hover:scale-[1.02]' : 'cursor-default'}
                  ${style.animate ? 'animate-pulse' : ''}
                `}
                title={isClickable ? `Click to view ${node.label} output` : undefined}
              >
                {/* Icon */}
                <span className="text-2xl mb-1">{node.icon}</span>

                {/* Label */}
                <span className={`text-[11px] font-semibold text-center leading-tight ${style.text}`}>
                  {node.label}
                </span>

                {/* Elapsed time */}
                {elapsed && (
                  <span className="text-[10px] text-gray-400 mt-0.5">{elapsed}</span>
                )}

                {/* Status pill */}
                <span className={`
                  mt-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold
                  ${style.pill} ${style.pillText}
                `}>
                  {PILL_LABELS[visualStatus]}
                </span>

                {/* Click hint for completed */}
                {isClickable && (
                  <span className="absolute -top-1.5 -right-1.5 text-xs bg-white rounded-full shadow border border-green-200 w-5 h-5 flex items-center justify-center">
                    🔗
                  </span>
                )}
              </button>

              {/* Arrow connector (not after last node) */}
              {idx < PIPELINE_NODES.length - 1 && (
                <div className="flex items-center px-1">
                  <svg width="20" height="12" viewBox="0 0 20 12" className="text-gray-300">
                    <path
                      d="M0 6 L14 6 M10 1 L16 6 L10 11"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Contextual status footer */}
      {(() => {
        const qvStep = agentSteps.find((s) => s.name === 'quality_validator')
        const sgStep = agentSteps.find((s) => s.name === 'slide_generator')
        const inQualityLoop = isValidationFailed(qvStep) && sgStep?.status === 'running'
        const anyRunning = agentSteps.some((s) => s.status === 'running')
        const runningNode = PIPELINE_NODES.find((n) => getStepStatus(agentSteps, n.name) === 'running')

        if (inQualityLoop) {
          // Extract violation count from summary if available
          const violations = qvStep?.output_summary?.match(/\d+(?= violation)/) ?? null
          return (
            <div className="mt-3 space-y-1.5">
              <div className="flex items-start gap-2 rounded-lg bg-orange-50 border border-orange-200 px-3 py-2">
                <span className="text-base shrink-0">⚠️</span>
                <div>
                  <p className="text-sm font-semibold text-orange-800">
                    Validation failed{violations ? ` — ${violations} violation${parseInt(violations[0]) !== 1 ? 's' : ''} found` : ''}
                  </p>
                  <p className="text-xs text-orange-700 mt-0.5">
                    Slides are being regenerated to address the issues. The pipeline will re-validate automatically.
                  </p>
                </div>
              </div>
            </div>
          )
        }

        if (anyRunning && runningNode) {
          return (
            <div className="mt-3 flex items-center gap-2 text-sm text-blue-600">
              <span className="animate-spin text-base">⏳</span>
              <span className="font-medium">{runningNode.label}…</span>
            </div>
          )
        }

        return null
      })()}
    </div>
  )
}
