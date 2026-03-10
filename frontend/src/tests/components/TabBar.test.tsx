/**
 * TabBar component tests.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TabBar from '@/components/TabBar'
import { useStore } from '@/store'

beforeEach(() => {
  useStore.setState({
    activeTab: 'intake',
    envelope: null,
    status: null,
    setTab: useStore.getState().setTab,
  })
})

describe('TabBar', () => {
  it('renders all 3 tabs', () => {
    render(<TabBar />)
    expect(screen.getByText('Intake')).toBeInTheDocument()
    expect(screen.getByText('Gallery')).toBeInTheDocument()
    expect(screen.getByText('Export')).toBeInTheDocument()
  })

  it('highlights the active tab (aria-selected)', () => {
    render(<TabBar />)
    const intakeTab = screen.getByRole('tab', { name: /intake/i })
    expect(intakeTab).toHaveAttribute('aria-selected', 'true')
  })

  it('Gallery and Export are disabled when no deck', () => {
    render(<TabBar />)
    const galleryTab = screen.getByRole('tab', { name: /gallery/i })
    const exportTab = screen.getByRole('tab', { name: /export/i })
    expect(galleryTab).toBeDisabled()
    expect(exportTab).toBeDisabled()
  })

  it('Gallery is enabled when envelope is set', () => {
    useStore.setState({ envelope: { session_id: 'x', status: 'completed', deck: null, created_at: '' } })
    render(<TabBar />)
    const galleryTab = screen.getByRole('tab', { name: /gallery/i })
    expect(galleryTab).not.toBeDisabled()
  })

  it('switches tab on click', () => {
    useStore.setState({ envelope: { session_id: 'x', status: 'completed', deck: null, created_at: '' }, status: 'completed' })
    render(<TabBar />)
    fireEvent.click(screen.getByRole('tab', { name: /gallery/i }))
    expect(useStore.getState().activeTab).toBe('gallery')
  })

  it('Intake tab is always enabled', () => {
    render(<TabBar />)
    const intakeTab = screen.getByRole('tab', { name: /intake/i })
    expect(intakeTab).not.toBeDisabled()
  })
})
