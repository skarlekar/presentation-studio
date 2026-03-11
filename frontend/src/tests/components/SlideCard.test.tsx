/**
 * SlideCard component tests.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SlideCard from '@/components/SlideCard'
import { mockSlide, mockAppendixSlide } from '@/tests/fixtures'
import { useStore } from '@/store'

// Reset store between tests
beforeEach(() => {
  useStore.setState({
    selectedSlideId: null,
    selectSlide: useStore.getState().selectSlide,
  })
})

describe('SlideCard', () => {
  it('renders slide ID and title', () => {
    render(<SlideCard slide={mockSlide} />)
    expect(screen.getByText('01')).toBeInTheDocument()
    expect(screen.getByText(/Cloud migration reduces TCO/)).toBeInTheDocument()
  })

  it('renders all key points in full (no truncation)', () => {
    render(<SlideCard slide={mockSlide} />)
    expect(screen.getByText(/Current on-prem costs/)).toBeInTheDocument()
  })

  it('renders metaphor with 💡 prefix', () => {
    render(<SlideCard slide={mockSlide} />)
    expect(screen.getByText(/Moving to the cloud is like/)).toBeInTheDocument()
  })

  it('renders takeaway field', () => {
    render(<SlideCard slide={mockSlide} />)
    // takeaway is rendered with 🎯 prefix
    expect(screen.getByText(/Migration pays for itself/)).toBeInTheDocument()
  })

  it('renders evidence type badges', () => {
    render(<SlideCard slide={mockSlide} />)
    expect(screen.getByText('metric')).toBeInTheDocument()
    expect(screen.getByText('case_study')).toBeInTheDocument()
  })

  it('renders section label', () => {
    render(<SlideCard slide={mockSlide} />)
    expect(screen.getByText('Setup')).toBeInTheDocument()
  })

  it('selects slide on click via store', () => {
    render(<SlideCard slide={mockSlide} />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    expect(useStore.getState().selectedSlideId).toBe('01')
  })

  it('deselects slide on second click', () => {
    render(<SlideCard slide={mockSlide} />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    fireEvent.click(btn)
    expect(useStore.getState().selectedSlideId).toBeNull()
  })

  it('shows aria-pressed=true when selected', () => {
    useStore.setState({ selectedSlideId: '01' })
    render(<SlideCard slide={mockSlide} />)
    const btn = screen.getByRole('button')
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('renders appendix slide with isAppendix flag', () => {
    render(<SlideCard slide={mockAppendixSlide} isAppendix />)
    expect(screen.getByText('A01')).toBeInTheDocument()
    expect(screen.getByText('Appendix')).toBeInTheDocument()
  })
})
