/**
 * usePolling hook tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePolling } from '@/hooks/usePolling'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('usePolling', () => {
  it('does not call onTick when disabled', async () => {
    const onTick = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling({ enabled: false, onTick, intervalMs: 100 }))
    await act(async () => { vi.advanceTimersByTime(500) })
    expect(onTick).not.toHaveBeenCalled()
  })

  it('calls onTick after interval when enabled', async () => {
    const onTick = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling({ enabled: true, onTick, intervalMs: 100 }))
    await act(async () => { vi.advanceTimersByTime(150) })
    expect(onTick).toHaveBeenCalledTimes(1)
  })

  it('stops polling when onTick returns true', async () => {
    const onTick = vi.fn().mockResolvedValue(true)
    renderHook(() => usePolling({ enabled: true, onTick, intervalMs: 100 }))
    await act(async () => { vi.advanceTimersByTime(500) })
    expect(onTick).toHaveBeenCalledTimes(1)
  })

  it('calls onError when onTick throws', async () => {
    const onTick = vi.fn().mockRejectedValue(new Error('network'))
    const onError = vi.fn()
    renderHook(() => usePolling({ enabled: true, onTick, onError, intervalMs: 100 }))
    await act(async () => { vi.advanceTimersByTime(150) })
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('stops polling when disabled changes to false', async () => {
    const onTick = vi.fn().mockResolvedValue(undefined)
    let enabled = true
    const { rerender } = renderHook(({ en }) =>
      usePolling({ enabled: en, onTick, intervalMs: 100 }),
      { initialProps: { en: enabled } },
    )

    await act(async () => { vi.advanceTimersByTime(150) })
    expect(onTick).toHaveBeenCalledTimes(1)

    rerender({ en: false })
    await act(async () => { vi.advanceTimersByTime(300) })
    // Should not be called any more after disabling
    expect(onTick).toHaveBeenCalledTimes(1)
  })

  it('polls multiple times while enabled', async () => {
    const onTick = vi.fn().mockResolvedValue(undefined)
    renderHook(() => usePolling({ enabled: true, onTick, intervalMs: 100 }))
    await act(async () => { vi.advanceTimersByTime(350) })
    expect(onTick).toHaveBeenCalledTimes(3)
  })
})
