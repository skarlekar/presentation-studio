/**
 * AgentStatusBadge component tests.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AgentStatusBadge from '@/components/AgentStatusBadge'

describe('AgentStatusBadge', () => {
  it('renders nothing when status is null', () => {
    const { container } = render(<AgentStatusBadge status={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders "Running" for running status', () => {
    render(<AgentStatusBadge status="running" />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('renders "Complete" for completed status', () => {
    render(<AgentStatusBadge status="completed" />)
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('renders "Awaiting Your Review" for awaiting_approval', () => {
    render(<AgentStatusBadge status="awaiting_approval" />)
    expect(screen.getByText('Awaiting Your Review')).toBeInTheDocument()
  })

  it('renders "Failed" for failed status', () => {
    render(<AgentStatusBadge status="failed" />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('shows stage label when stage prop provided', () => {
    render(<AgentStatusBadge status="running" stage="insight_extractor" />)
    expect(screen.getByText(/Stage 1\/5/)).toBeInTheDocument()
  })

  it('shows progress bar when progressPct between 1 and 99', () => {
    render(<AgentStatusBadge status="running" progressPct={45} />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '45')
  })

  it('does not show progress bar when progressPct is 0', () => {
    render(<AgentStatusBadge status="pending" progressPct={0} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('does not show progress bar when progressPct is 100', () => {
    render(<AgentStatusBadge status="completed" progressPct={100} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('renders error message', () => {
    render(<AgentStatusBadge status="failed" error="Pipeline timeout" />)
    expect(screen.getByText('Pipeline timeout')).toBeInTheDocument()
  })
})
