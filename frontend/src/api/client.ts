/**
 * DeckStudio API client.
 * All fetch calls go through this module so base URL and error handling
 * are centralized. No external HTTP library required.
 */

import type {
  DeckRequest,
  GenerateResponse,
  SessionStatusResponse,
  DeckEnvelope,
  CheckpointApproveRequest,
  CheckpointRejectRequest,
  Slide,
  ValidationReport,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

// ── Helpers ──────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`)
    this.name = 'ApiError'
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE_URL}${path}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      detail = err.detail ?? err.message ?? JSON.stringify(err)
    } catch {
      // ignore parse error — use statusText
    }
    throw new ApiError(res.status, detail)
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

// ── Deck generation ───────────────────────────────────────────────────────────

/** Start a new deck generation pipeline. Returns session_id immediately. */
export async function generateDeck(req: DeckRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>('POST', '/api/deck/generate', req)
}

/** Check server health and whether the API key is pre-configured. */

/** Upload a source material file and start generation. */
export async function generateDeckWithUpload(
  file: File,
  req: Omit<DeckRequest, 'source_material'>,
): Promise<GenerateResponse> {
  const url = `${BASE_URL}/api/deck/generate/upload`
  const form = new FormData()
  form.append('file', file)
  form.append('context', req.context ?? '')
  form.append('number_of_slides', String(req.number_of_slides))
  form.append('audience', req.audience)
  form.append('deck_type', req.deck_type)
  form.append('decision_inform_ask', req.decision_inform_ask)
  form.append('tone', req.tone)

  const res = await fetch(url, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      detail = err.detail ?? err.message ?? JSON.stringify(err)
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }

  return res.json()
}

// ── Session status polling ────────────────────────────────────────────────────

/** Poll the session status. Returns 200 with checkpoint if paused, 200 completed, 200 failed. */
export async function getSessionStatus(
  sessionId: string,
): Promise<SessionStatusResponse> {
  return request<SessionStatusResponse>('GET', `/api/deck/${sessionId}/status`)
}

// ── Deck retrieval ───────────────────────────────────────────────────────────

/** Fetch the completed deck. Returns 202 body if still running. */
export async function getDeck(sessionId: string): Promise<DeckEnvelope | null> {
  const res = await fetch(`${BASE_URL}/api/deck/${sessionId}`, {
    headers: { Accept: 'application/json' },
  })

  if (res.status === 202) return null // still processing
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = await res.json()
      detail = err.detail ?? JSON.stringify(err)
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }

  return res.json()
}

// ── HITL checkpoints ─────────────────────────────────────────────────────────

/** Approve a checkpoint and resume the pipeline. */
export async function approveCheckpoint(
  sessionId: string,
  checkpointId: string,
  body: CheckpointApproveRequest = {},
): Promise<{ status: string; checkpoint_id: string }> {
  return request('POST', `/api/deck/${sessionId}/checkpoint/${checkpointId}/approve`, body)
}

/** Reject a checkpoint — halts the pipeline. */
export async function rejectCheckpoint(
  sessionId: string,
  checkpointId: string,
  feedback: string,
): Promise<{ status: string; feedback: string }> {
  const body: CheckpointRejectRequest = { feedback }
  return request('POST', `/api/deck/${sessionId}/checkpoint/${checkpointId}/reject`, body)
}

// ── Slide editing ─────────────────────────────────────────────────────────────

/** Update a single slide field and get back the updated slide + validation. */
export async function updateSlide(
  sessionId: string,
  slideId: string,
  field: string,
  value: unknown,
): Promise<{ slide: Slide; validation: ValidationReport }> {
  return request('PUT', `/api/deck/${sessionId}/slide/${slideId}`, {
    session_id: sessionId,
    slide_id: slideId,
    field,
    value,
  })
}

// ── Approval + Export ─────────────────────────────────────────────────────────

/** Mark the deck as human-approved. */
export async function approveDeck(
  sessionId: string,
): Promise<{ status: string; export_ready: boolean; session_id: string }> {
  return request('POST', `/api/deck/${sessionId}/approve`)
}

/** Export the approved deck to a versioned JSON file. */
export async function exportDeck(sessionId: string): Promise<{
  filename: string
  filepath: string
  version: number
  saved_at: string
  size_bytes: number
}> {
  return request('POST', `/api/deck/${sessionId}/export`)
}

/** Get all exported versions for a session. */
export async function getDeckHistory(
  sessionId: string,
): Promise<{ versions: Array<{ filename: string; version: number; saved_at: string; size_bytes: number }>; session_id: string }> {
  return request('GET', `/api/deck/${sessionId}/history`)
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{
  status: string
  version: string
  api_key_configured: boolean
  llm_provider: string
  llm_model: string
}> {
  return request('GET', '/api/health')
}
