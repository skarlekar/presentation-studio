/**
 * CheckpointModal component tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import CheckpointModal from '@/components/CheckpointModal'
import { useStore } from '@/store'
import { mockCheckpoint } from '@/tests/fixtures'

// Mock useDeck
vi.mock('@/hooks/useDeck', () => ({
  useDeck: () => ({
    approve: vi.fn().mockResolvedValue(undefined),
    reject: vi.fn().mockResolvedValue(undefined),
  }),
}))

beforeEach(() => {
  useStore.setState({
    checkpoint: mockCheckpoint,
    checkpointModalOpen: true,
    closeCheckpointModal: useStore.getState().closeCheckpointModal,
  })
})

describe('CheckpointModal', () => {
  it('renders checkpoint label', () => {
    render(<CheckpointModal />)
    expect(screen.getByText('Confirm Core Insights')).toBeInTheDocument()
  })

  it('renders stage info', () => {
    render(<CheckpointModal />)
    expect(screen.getByText(/Stage 1 of 5/)).toBeInTheDocument()
  })

  it('renders "Human-in-the-loop checkpoint" label', () => {
    render(<CheckpointModal />)
    expect(screen.getByText(/Human-in-the-loop checkpoint/i)).toBeInTheDocument()
  })

  it('shows Approve and Reject buttons', () => {
    render(<CheckpointModal />)
    expect(screen.getByText(/Approve & Continue/)).toBeInTheDocument()
    expect(screen.getByText(/Reject & Revise/)).toBeInTheDocument()
  })

  it('switches to reject mode on Reject click', () => {
    render(<CheckpointModal />)
    fireEvent.click(screen.getByText(/Reject & Revise/))
    expect(screen.getByPlaceholderText(/Be specific/)).toBeInTheDocument()
  })

  it('Submit Rejection is disabled if feedback < 10 chars', () => {
    render(<CheckpointModal />)
    fireEvent.click(screen.getByText(/Reject & Revise/))
    const submitBtn = screen.getByText(/Submit Rejection/)
    expect(submitBtn).toBeDisabled()
  })

  it('Submit Rejection enabled when feedback >= 10 chars', () => {
    render(<CheckpointModal />)
    fireEvent.click(screen.getByText(/Reject & Revise/))
    const textarea = screen.getByPlaceholderText(/Be specific/)
    fireEvent.change(textarea, { target: { value: 'Titles are not conclusion statements — fix them' } })
    expect(screen.getByText(/Submit Rejection/)).not.toBeDisabled()
  })

  it('goes back to review mode on Back click', () => {
    render(<CheckpointModal />)
    fireEvent.click(screen.getByText(/Reject & Revise/))
    fireEvent.click(screen.getByText('← Back'))
    expect(screen.getByText(/Approve & Continue/)).toBeInTheDocument()
  })

  it('renders nothing when checkpoint is null', () => {
    useStore.setState({ checkpoint: null })
    const { container } = render(<CheckpointModal />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders JSON preview of pending_input', () => {
    render(<CheckpointModal />)
    expect(screen.getByText(/core_problem/)).toBeInTheDocument()
  })
})
