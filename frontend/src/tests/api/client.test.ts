/**
 * API client tests — mock fetch and verify correct requests are made.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  generateDeck,
  getSessionStatus,
  approveCheckpoint,
  rejectCheckpoint,
  exportDeck,
  checkHealth,
  ApiError,
} from '@/api/client'
import { mockEnvelope, mockStatusCompleted } from '@/tests/fixtures'

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }))
;(globalThis as any).fetch = mockFetch

function mockOk(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    status,
    json: () => Promise.resolve(body),
  })
}

function mockError(status: number, detail: string) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    statusText: `HTTP ${status}`,
    json: () => Promise.resolve({ detail }),
  })
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('generateDeck', () => {
  it('POSTs to /api/deck/generate and returns session_id', async () => {
    mockOk({ session_id: 'sess-001', status: 'accepted', stream_url: '/api/deck/sess-001/status' }, 202)

    const result = await generateDeck({
      context: 'Test context',
      number_of_slides: 11,
      audience: 'C-suite',
      deck_type: 'Decision Deck',
      decision_inform_ask: 'Decision',
      tone: 'Authoritative',
    })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/deck/generate'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(result.session_id).toBe('sess-001')
  })

  it('throws ApiError on 422', async () => {
    mockError(422, 'context or source_material required')
    await expect(
      generateDeck({
        context: null,
        number_of_slides: 11,
        audience: 'C-suite',
        deck_type: 'Decision Deck',
        decision_inform_ask: 'Decision',
        tone: 'Authoritative',
      } as never),
    ).rejects.toThrow(ApiError)
  })
})

describe('getSessionStatus', () => {
  it('GETs /api/deck/{id}/status and returns status response', async () => {
    mockOk(mockStatusCompleted)
    const result = await getSessionStatus('test-session-123')
    expect(result.status).toBe('completed')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/deck/test-session-123/status'),
      expect.any(Object),
    )
  })

  it('throws ApiError 404 when session not found', async () => {
    mockError(404, 'Session not found')
    await expect(getSessionStatus('nonexistent')).rejects.toThrow(ApiError)
  })
})

describe('approveCheckpoint', () => {
  it('POSTs to correct approve URL', async () => {
    mockOk({ status: 'advancing', checkpoint_id: 'cp-123' })
    const result = await approveCheckpoint('sess-001', 'cp-123', { comment: 'Looks good' })
    expect(result.status).toBe('advancing')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/deck/sess-001/checkpoint/cp-123/approve'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('rejectCheckpoint', () => {
  it('POSTs feedback to reject URL', async () => {
    mockOk({ status: 'rejected', feedback: 'Titles are not conclusion statements' })
    const result = await rejectCheckpoint('sess-001', 'cp-123', 'Titles are not conclusion statements')
    expect(result.status).toBe('rejected')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/deck/sess-001/checkpoint/cp-123/reject'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('exportDeck', () => {
  it('POSTs to export endpoint and returns file metadata', async () => {
    mockOk({
      filename: 'cloud-migration_20260310_180000_v1.json',
      filepath: '/opt/deckstudio/data/exports/cloud-migration_20260310_180000_v1.json',
      version: 1,
      saved_at: '2026-03-10T18:00:00Z',
      size_bytes: 45320,
    })
    const result = await exportDeck('sess-001')
    expect(result.version).toBe(1)
    expect(result.filename).toContain('v1.json')
  })
})

describe('checkHealth', () => {
  it('GETs /api/health and returns ok status', async () => {
    mockOk({ status: 'ok', version: '1.0.0' })
    const result = await checkHealth()
    expect(result.status).toBe('ok')
  })
})

describe('ApiError', () => {
  it('has correct name, status, and message', () => {
    const err = new ApiError(404, 'Not found')
    expect(err.name).toBe('ApiError')
    expect(err.status).toBe(404)
    expect(err.message).toContain('404')
    expect(err.message).toContain('Not found')
  })
})
