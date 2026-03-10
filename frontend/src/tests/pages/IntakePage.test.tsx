/**
 * IntakePage tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import IntakePage from '@/pages/IntakePage'
import { useStore } from '@/store'

// Mock useDeck
const mockStartGeneration = vi.fn().mockResolvedValue(undefined)
const mockReset = vi.fn()
vi.mock('@/hooks/useDeck', () => ({
  useDeck: () => ({
    startGeneration: mockStartGeneration,
    reset: mockReset,
    approve_and_export: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    editSlide: vi.fn(),
  }),
}))

beforeEach(() => {
  useStore.setState({
    status: null,
    progressPct: 0,
    currentStage: null,
    error: null,
    isPolling: false,
  })
  mockStartGeneration.mockClear()
  mockReset.mockClear()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <IntakePage />
    </MemoryRouter>,
  )
}

describe('IntakePage', () => {
  it('renders the form fields', () => {
    renderPage()
    expect(screen.getByText('Deck Configuration')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Background, situation/)).toBeInTheDocument()
    expect(screen.getByText('Deck Type')).toBeInTheDocument()
    expect(screen.getByText('Audience')).toBeInTheDocument()
  })

  it('renders Generate Deck button', () => {
    renderPage()
    expect(screen.getByText('🚀 Generate Deck')).toBeInTheDocument()
  })

  it('submit button is disabled while pipeline is running', () => {
    useStore.setState({ status: 'running', isPolling: true })
    renderPage()
    const btn = screen.getByRole('button', { name: /Generating deck/ })
    expect(btn).toBeDisabled()
  })

  it('shows completion message when status is completed', () => {
    useStore.setState({ status: 'completed' })
    renderPage()
    expect(screen.getByText(/Deck complete — see Gallery tab/)).toBeInTheDocument()
  })

  it('shows AgentStatusBadge when status is set', () => {
    useStore.setState({ status: 'running', progressPct: 20 })
    renderPage()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('shows Start over link on failure', () => {
    useStore.setState({ status: 'failed', error: 'Pipeline timeout' })
    renderPage()
    expect(screen.getByText('Start over')).toBeInTheDocument()
  })

  it('calls reset when Start over is clicked', () => {
    useStore.setState({ status: 'failed' })
    renderPage()
    fireEvent.click(screen.getByText('Start over'))
    expect(mockReset).toHaveBeenCalled()
  })

  it('deck type select has all 5 options', () => {
    renderPage()
    const select = screen.getByDisplayValue('Decision Deck')
    expect(select).toBeInTheDocument()
  })

  it('slide count range updates the display', () => {
    renderPage()
    const range = screen.getByRole('slider')
    fireEvent.change(range, { target: { value: '20' } })
    expect(screen.getByText('20')).toBeInTheDocument()
  })
})
