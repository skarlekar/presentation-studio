/**
 * useDeck — orchestrates polling, checkpoint handling, and deck operations.
 *
 * Zustand pattern: use `useStore.getState()` inside callbacks (stable, no re-renders).
 * Use individual selectors for state values that drive renders.
 */
import { useCallback } from 'react'
import { useStore } from '@/store'
import { usePolling } from '@/hooks/usePolling'
import {
  generateDeck,
  getSessionStatus,
  getDeck,
  approveCheckpoint,
  rejectCheckpoint,
  updateSlide,
  approveDeck,
  exportDeck,
  checkHealth,
  ApiError,
} from '@/api/client'
import type { DeckRequest, CheckpointApproveRequest } from '@/types'

export function useDeck() {
  // ── State selectors (stable if selected value doesn't change) ──────────────
  const sessionId    = useStore(s => s.sessionId)
  const status       = useStore(s => s.status)
  const currentStage = useStore(s => s.currentStage)
  const progressPct  = useStore(s => s.progressPct)
  const checkpoint   = useStore(s => s.checkpoint)
  const error        = useStore(s => s.error)
  const isPolling    = useStore(s => s.isPolling)
  const envelope     = useStore(s => s.envelope)
  const exportResult = useStore(s => s.exportResult)
  const apiKey       = useStore(s => s.apiKey)
  const apiKeyConfigured = useStore(s => s.apiKeyConfigured)
  const apiKeyChecked    = useStore(s => s.apiKeyChecked)

  // ── Health check (one-time on mount) ───────────────────────────────────────
  // Uses getState() so deps array can be empty — no infinite loop.

  const checkApiKeyStatus = useCallback(async () => {
    try {
      const health = await checkHealth()
      useStore.getState().setApiKeyStatus(health.api_key_configured)
    } catch {
      useStore.getState().setApiKeyStatus(false)
    }
  }, []) // stable — intentionally empty deps

  // ── Start pipeline ──────────────────────────────────────────────────────────

  const startGeneration = useCallback(async (req: DeckRequest) => {
    const { apiKey: key, apiKeyConfigured: configured, startSession, updateFromStatus } =
      useStore.getState()
    try {
      const reqWithKey: DeckRequest =
        key && !configured ? { ...req, api_key: key } : req
      const resp = await generateDeck(reqWithKey)
      startSession(resp.session_id, reqWithKey)
    } catch (err) {
      updateFromStatus({
        session_id: '',
        status: 'failed',
        error: err instanceof ApiError ? err.detail : String(err),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    }
  }, [])

  // ── Poll session status ─────────────────────────────────────────────────────

  const pollTick = useCallback(async (): Promise<boolean | void> => {
    const { sessionId: sid, updateFromStatus, setPolling, setEnvelope } =
      useStore.getState()
    if (!sid) return true

    try {
      const statusResp = await getSessionStatus(sid)
      updateFromStatus(statusResp)

      const terminal = ['completed', 'complete', 'failed', 'cancelled', 'rejected']
      if (terminal.includes(statusResp.status)) {
        if (statusResp.status === 'completed' || statusResp.status === 'complete') {
          const env = await getDeck(sid)
          if (env) setEnvelope(env)
        }
        setPolling(false)
        return true
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        useStore.getState().setPolling(false)
        return true
      }
      console.warn('[useDeck] Poll error:', err)
    }
  }, [])

  usePolling({ enabled: isPolling, onTick: pollTick })

  // ── Checkpoint operations ───────────────────────────────────────────────────

  const approve = useCallback(async (body: CheckpointApproveRequest = {}) => {
    const { sessionId: sid, checkpoint: cp, closeCheckpointModal, setPolling } =
      useStore.getState()
    if (!sid || !cp) return
    try {
      await approveCheckpoint(sid, cp.checkpoint_id, body)
      closeCheckpointModal()
      setPolling(true)
    } catch (err) {
      console.error('[useDeck] Approve error:', err)
    }
  }, [])

  const reject = useCallback(async (feedback: string) => {
    const { sessionId: sid, checkpoint: cp, closeCheckpointModal, updateFromStatus } =
      useStore.getState()
    if (!sid || !cp) return
    try {
      await rejectCheckpoint(sid, cp.checkpoint_id, feedback)
      closeCheckpointModal()
      updateFromStatus({
        session_id: sid,
        status: 'rejected',
        error: `Rejected: ${feedback}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    } catch (err) {
      console.error('[useDeck] Reject error:', err)
    }
  }, [])

  // ── Slide editing ───────────────────────────────────────────────────────────

  const editSlide = useCallback(
    async (slideId: string, field: string, value: unknown) => {
      const { sessionId: sid, updateSlideInStore } = useStore.getState()
      if (!sid) return null
      try {
        const result = await updateSlide(sid, slideId, field, value)
        if (result?.slide) updateSlideInStore(result.slide)
        return result?.validation ?? null
      } catch (err) {
        console.error('[useDeck] Edit slide error:', err)
        return null
      }
    },
    [],
  )

  // ── Export ──────────────────────────────────────────────────────────────────

  const approve_and_export = useCallback(async () => {
    const { sessionId: sid, envelope, setExportResult, setTab, setError } = useStore.getState()
    if (!sid) {
      setError('No active session — please reload the deck from the Gallery tab.')
      return null
    }
    try {
      // If the session no longer exists on the backend (e.g. after a server restart),
      // re-register it from the in-memory envelope before exporting.
      let activeSid = sid
      try {
        await approveDeck(activeSid)
      } catch (approveErr) {
        if (approveErr instanceof ApiError && approveErr.status === 404 && envelope) {
          // Session gone from backend — restore it then retry
          const { restoreSession } = await import('@/api/client')
          const restored = await restoreSession({ session_id: sid, ...JSON.parse(JSON.stringify(envelope)) })
          activeSid = restored.session_id
          useStore.getState().setSessionId(activeSid)
          await approveDeck(activeSid)
        } else {
          throw approveErr
        }
      }
      const result = await exportDeck(activeSid)
      setExportResult(result)
      setTab('export')
      return result
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : String(err)
      console.error('[useDeck] Export error:', err)
      useStore.getState().setError(`Export failed: ${msg}`)
      return null
    }
  }, [])

  const reset = useCallback(() => {
    useStore.getState().resetSession()
  }, [])

  return {
    // State
    sessionId,
    status,
    currentStage,
    progressPct,
    checkpoint,
    error,
    isPolling,
    envelope,
    exportResult,
    apiKey,
    apiKeyConfigured,
    apiKeyChecked,

    // Actions
    startGeneration,
    approve,
    reject,
    editSlide,
    approve_and_export,
    reset,
    checkApiKeyStatus,
  }
}
