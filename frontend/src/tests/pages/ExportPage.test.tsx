/**
 * ExportPage tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ExportPage from '@/pages/ExportPage'
import { useStore } from '@/store'
import { mockEnvelope } from '@/tests/fixtures'

const mockApproveAndExport = vi.fn().mockResolvedValue({ filename: 'deck_v1.json', version: 1, saved_at: '2026-03-10T18:00:00Z', size_bytes: 12345 })

vi.mock('@/hooks/useDeck', () => ({
  useDeck: () => ({
    approve_and_export: mockApproveAndExport,
    startGeneration: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    editSlide: vi.fn(),
    reset: vi.fn(),
  }),
}))

// Mock getDeckHistory
vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  return {
    ...original,
    getDeckHistory: vi.fn().mockResolvedValue({ versions: [], session_id: 'test' }),
  }
})

beforeEach(() => {
  useStore.setState({
    envelope: null,
    exportResult: null,
    sessionId: null,
  })
  mockApproveAndExport.mockClear()
})

describe('ExportPage — no deck', () => {
  it('shows "Nothing to export yet" when no deck', () => {
    render(<ExportPage />)
    expect(screen.getByText('Nothing to export yet')).toBeInTheDocument()
  })
})

describe('ExportPage — with deck', () => {
  beforeEach(() => {
    useStore.setState({
      envelope: mockEnvelope,
      sessionId: 'test-session-123',
    })
  })

  it('renders deck title', () => {
    render(<ExportPage />)
    expect(screen.getByText('Cloud Migration Business Case')).toBeInTheDocument()
  })

  it('renders Approve & Export JSON button', () => {
    render(<ExportPage />)
    expect(screen.getByText(/Approve & Export JSON/)).toBeInTheDocument()
  })

  it('renders JSON preview section', () => {
    render(<ExportPage />)
    expect(screen.getByLabelText('Deck JSON preview')).toBeInTheDocument()
  })

  it('shows slide stats', () => {
    render(<ExportPage />)
    expect(screen.getByText('Main Slides')).toBeInTheDocument()
    expect(screen.getByText('Appendix Slides')).toBeInTheDocument()
    expect(screen.getByText('Evidence Items')).toBeInTheDocument()
  })

  it('calls approve_and_export on button click', async () => {
    render(<ExportPage />)
    fireEvent.click(screen.getByText(/Approve & Export JSON/))
    await waitFor(() => expect(mockApproveAndExport).toHaveBeenCalled())
  })

  it('shows export success banner when exportResult is set', () => {
    useStore.setState({
      exportResult: {
        filename: 'cloud-migration_v1.json',
        version: 1,
        saved_at: '2026-03-10T18:00:00Z',
        size_bytes: 45320,
      },
    })
    render(<ExportPage />)
    expect(screen.getByText('Export successful')).toBeInTheDocument()
    expect(screen.getByText('cloud-migration_v1.json')).toBeInTheDocument()
  })

  it('shows "No exports yet" when version history is empty', async () => {
    render(<ExportPage />)
    await waitFor(() => {
      expect(screen.getByText(/No exports yet/)).toBeInTheDocument()
    })
  })
})
