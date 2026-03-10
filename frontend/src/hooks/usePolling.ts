/**
 * usePolling — polls a resource on a fixed interval and stops when done.
 */
import { useEffect, useRef, useCallback } from 'react'

interface UsePollingOptions {
  /** Interval between polls in ms (default: VITE_POLL_INTERVAL_MS or 2000) */
  intervalMs?: number
  /** When true, polling is active */
  enabled: boolean
  /** Called on each tick; must throw or return a "stop" signal to halt */
  onTick: () => Promise<boolean | void>
  /** Called if onTick throws */
  onError?: (err: unknown) => void
}

const DEFAULT_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 2000

export function usePolling({
  intervalMs = DEFAULT_INTERVAL,
  enabled,
  onTick,
  onError,
}: UsePollingOptions): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onTickRef = useRef(onTick)
  const onErrorRef = useRef(onError)
  const enabledRef = useRef(enabled)

  // Keep refs current without re-registering the effect
  onTickRef.current = onTick
  onErrorRef.current = onError
  enabledRef.current = enabled

  const scheduleNext = useCallback(() => {
    timerRef.current = setTimeout(async () => {
      if (!enabledRef.current) return

      try {
        const stop = await onTickRef.current()
        if (stop === true) return // Caller signals "stop"
      } catch (err) {
        onErrorRef.current?.(err)
      }

      // Schedule next tick only if still enabled
      if (enabledRef.current) {
        scheduleNext()
      }
    }, intervalMs)
  }, [intervalMs])

  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
      return
    }

    scheduleNext()

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [enabled, scheduleNext])
}
