/**
 * useDeck — orchestrates polling, checkpoint handling, and deck operations.
 * Components use this hook instead of calling the API directly.
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
  ApiError,
} from '@/api/client'
import type { DeckRequest, CheckpointApproveRequest } from '@/types'

export function useDeck() {
  const store = useStore()

  // ── Start pipeline ──────────────────────────────────────────────────────────

  const startGeneration = useCallback(async (req: DeckRequest) => {
    try {
      const resp = await generateDeck(req)
      store.startSession(resp.session_id, req)
    } catch (err) {
      store.updateFromStatus({
        session_id: '',
        status: 'failed',
        error: err instanceof ApiError ? err.detail : String(err),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    }
  }, [store])

  // ── Poll session status ─────────────────────────────────────────────────────

  const pollTick = useCallback(async (): Promise<boolean | void> => {
    if (!store.sessionId) return true // stop

    try {
      const statusResp = await getSessionStatus(store.sessionId)
      store.updateFromStatus(statusResp)

      const terminal = ['completed', 'complete', 'failed', 'cancelled', 'rejected']
      if (terminal.includes(statusResp.status)) {
        // Fetch the full deck if completed
        if (statusResp.status === 'completed' || statusResp.status === 'complete') {
          const envelope = await getDeck(store.sessionId)
          if (envelope) {
            store.setEnvelope(envelope)
          }
        }
        store.setPolling(false)
        return true // stop polling
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        store.setPolling(false)
        return true
      }
      // Non-fatal: keep polling
      console.warn('[useDeck] Poll error:', err)
    }
  }, [store])

  usePolling({
    enabled: store.isPolling,
    onTick: pollTick,
  })

  // ── Checkpoint operations ───────────────────────────────────────────────────

  const approve = useCallback(
    async (body: CheckpointApproveRequest = {}) => {
      if (!store.sessionId || !store.checkpoint) return
      try {
        await approveCheckpoint(store.sessionId, store.checkpoint.checkpoint_id, body)
        store.closeCheckpointModal()
        store.setPolling(true)
      } catch (err) {
        console.error('[useDeck] Approve error:', err)
      }
    },
    [store],
  )

  const reject = useCallback(
    async (feedback: string) => {
      if (!store.sessionId || !store.checkpoint) return
      try {
        await rejectCheckpoint(store.sessionId, store.checkpoint.checkpoint_id, feedback)
        store.closeCheckpointModal()
        store.updateFromStatus({
          session_id: store.sessionId,
          status: 'rejected',
          error: `Rejected: ${feedback}`,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
      } catch (err) {
        console.error('[useDeck] Reject error:', err)
      }
    },
    [store],
  )

  // ── Slide editing ───────────────────────────────────────────────────────────

  const editSlide = useCallback(
    async (slideId: string, field: string, value: unknown) => {
      if (!store.sessionId) return null
      try {
        const result = await updateSlide(store.sessionId, slideId, field, value)
        store.updateSlideInStore(result.slide)
        return result.validation
      } catch (err) {
        console.error('[useDeck] Edit slide error:', err)
        return null
      }
    },
    [store],
  )

  // ── Export ──────────────────────────────────────────────────────────────────

  const approve_and_export = useCallback(async () => {
    if (!store.sessionId) return
    try {
      await approveDeck(store.sessionId)
      const result = await exportDeck(store.sessionId)
      store.setExportResult(result)
      store.setTab('export')
      return result
    } catch (err) {
      console.error('[useDeck] Export error:', err)
      return null
    }
  }, [store])

  const reset = useCallback(() => {
    store.resetSession()
  }, [store])

  return {
    // State
    sessionId: store.sessionId,
    status: store.status,
    currentStage: store.currentStage,
    progressPct: store.progressPct,
    checkpoint: store.checkpoint,
    error: store.error,
    isPolling: store.isPolling,
    envelope: store.envelope,
    exportResult: store.exportResult,

    // Actions
    startGeneration,
    approve,
    reject,
    editSlide,
    approve_and_export,
    reset,
  }
}
