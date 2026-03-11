/**
 * GalleryPage tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import GalleryPage from '@/pages/GalleryPage'
import { useStore } from '@/store'
import { mockEnvelope } from '@/tests/fixtures'

const { mockApproveAndExport } = vi.hoisted(() => ({
  mockApproveAndExport: vi.fn().mockResolvedValue(undefined),
}))

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

// Mock the API calls made by GalleryPage
// listAllExports/loadExport are overridden per-test where needed
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    listAllExports: vi.fn().mockResolvedValue({ total: 0, exports: [] }),
    loadExport: vi.fn().mockResolvedValue({ envelope: {}, sessionId: 'test-session' }),
  }
})

beforeEach(() => {
  useStore.setState({
    envelope: null,
    status: null,
    currentStage: null,
    progressPct: 0,
    error: null,
    selectedSlideId: null,
    showAppendix: false,
  })
  mockApproveAndExport.mockClear()
})

describe('GalleryPage — no deck', () => {
  it('shows no-active-deck message when no session', async () => {
    render(<GalleryPage />)
    await waitFor(() => {
      expect(screen.getByText(/No active deck/)).toBeInTheDocument()
    })
  })

  it('prompts user to start from Intake or reload previous run', async () => {
    render(<GalleryPage />)
    await waitFor(() => {
      expect(screen.getByText(/Start a new deck from the Intake tab/)).toBeInTheDocument()
    })
  })

  it('shows AgentStatusBadge when pipeline is running', () => {
    useStore.setState({ status: 'running', progressPct: 40 })
    render(<GalleryPage />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('shows previous runs list when exports exist', async () => {
    const { listAllExports } = await import('@/api/client')
    vi.mocked(listAllExports).mockResolvedValueOnce({
      total: 1,
      exports: [{
        filename: 'test-deck.json',
        session_id: 'abc-123',
        title: 'Agentic AI Security',
        deck_type: 'Strategy Deck',
        total_slides: 5,
        appendix_slides: 3,
        saved_at: '2026-03-11T10:00:00Z',
        size_bytes: 12345,
      }],
    })
    render(<GalleryPage />)
    await waitFor(() => {
      expect(screen.getByText('Agentic AI Security')).toBeInTheDocument()
    })
    expect(screen.getByText('Load')).toBeInTheDocument()
  })

  it('shows "No previous exports" when list is empty', async () => {
    render(<GalleryPage />)
    await waitFor(() => {
      expect(screen.getByText(/No previous exports found/)).toBeInTheDocument()
    })
  })
})

describe('GalleryPage — with deck', () => {
  beforeEach(() => {
    useStore.setState({ envelope: mockEnvelope, status: 'completed' })
  })

  it('renders deck title', () => {
    render(<GalleryPage />)
    expect(screen.getByText('Cloud Migration Business Case')).toBeInTheDocument()
  })

  it('renders slide count badge', () => {
    render(<GalleryPage />)
    expect(screen.getByText('1 slides')).toBeInTheDocument()
  })

  it('renders main slide cards', () => {
    render(<GalleryPage />)
    expect(screen.getByText(/Cloud migration reduces TCO/)).toBeInTheDocument()
  })

  it('renders Approve & Export button', () => {
    render(<GalleryPage />)
    expect(screen.getByText(/Approve & Export/)).toBeInTheDocument()
  })

  it('calls approve_and_export on button click', () => {
    render(<GalleryPage />)
    fireEvent.click(screen.getByText(/Approve & Export/))
    expect(mockApproveAndExport).toHaveBeenCalled()
  })

  it('shows editor prompt when no slide selected', () => {
    render(<GalleryPage />)
    expect(screen.getByText('Select a slide to edit')).toBeInTheDocument()
  })

  it('renders slide editor when slide is selected', () => {
    useStore.setState({ selectedSlideId: '01' })
    render(<GalleryPage />)
    expect(screen.getByText('Slide 01')).toBeInTheDocument()
  })
})
