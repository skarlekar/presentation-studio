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

const STATUS_STYLES: Record<AgentStep['status'], {
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
}

const PILL_LABELS: Record<AgentStep['status'], string> = {
  pending: 'Pending',
  running: 'Running…',
  completed: 'Done',
  failed: 'Failed',
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
          const status = getStepStatus(agentSteps, node.name)
          const style = STATUS_STYLES[status]
          const step = agentSteps.find((s) => s.name === node.name)
          const elapsed = getElapsedTime(step)
          const isClickable = status === 'completed'

          return (
            <div key={node.name} className="flex items-center">
              {/* Node card */}
              <button
                onClick={() => handleNodeClick(node.name, status)}
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
                  {PILL_LABELS[status]}
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

      {/* Running agent detail */}
      {agentSteps.some((s) => s.status === 'running') && (
        <div className="mt-3 flex items-center gap-2 text-sm text-blue-600">
          <span className="animate-spin text-base">⏳</span>
          <span className="font-medium">
            {PIPELINE_NODES.find((n) => getStepStatus(agentSteps, n.name) === 'running')?.label ?? 'Processing'}
            …
          </span>
        </div>
      )}
    </div>
  )
}
