/**
 * GalleryPage tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import GalleryPage from '@/pages/GalleryPage'
import { useStore } from '@/store'
import { mockEnvelope } from '@/tests/fixtures'

const mockApproveAndExport = vi.fn().mockResolvedValue(undefined)
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
  it('shows placeholder when no status', () => {
    render(<GalleryPage />)
    expect(screen.getByText(/Start a deck from the Intake tab/)).toBeInTheDocument()
  })

  it('shows AgentStatusBadge when pipeline is running', () => {
    useStore.setState({ status: 'running', progressPct: 40 })
    render(<GalleryPage />)
    expect(screen.getByText('Running')).toBeInTheDocument()
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
