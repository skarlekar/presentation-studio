/**
 * AppendixSection component tests.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AppendixSection from '@/components/AppendixSection'
import { useStore } from '@/store'
import { mockEnvelope } from '@/tests/fixtures'

beforeEach(() => {
  useStore.setState({
    envelope: mockEnvelope,
    showAppendix: false,
    toggleAppendix: useStore.getState().toggleAppendix,
  })
})

describe('AppendixSection', () => {
  it('renders nothing when appendix is empty', () => {
    useStore.setState({
      envelope: {
        ...mockEnvelope,
        deck: {
          ...mockEnvelope.deck!,
          appendix: { slides: [] },
        },
      },
    })
    const { container } = render(<AppendixSection />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders toggle button with slide count', () => {
    render(<AppendixSection />)
    expect(screen.getByText('Appendix')).toBeInTheDocument()
    expect(screen.getByText('1 slide')).toBeInTheDocument()
  })

  it('appendix slides hidden by default (collapsed)', () => {
    render(<AppendixSection />)
    expect(screen.queryByText(/Detailed cost breakdown/)).not.toBeInTheDocument()
  })

  it('shows appendix slides after toggle', () => {
    render(<AppendixSection />)
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Detailed cost breakdown/)).toBeInTheDocument()
  })

  it('toggle button has aria-expanded', () => {
    render(<AppendixSection />)
    const btn = screen.getByRole('button')
    expect(btn).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
  })

  it('shows plural "slides" for multiple appendix slides', () => {
    const moreSlides = { ...mockEnvelope.deck!.appendix.slides[0], slide_id: 'A02', title: 'Another appendix slide with conclusion statement' }
    useStore.setState({
      envelope: {
        ...mockEnvelope,
        deck: {
          ...mockEnvelope.deck!,
          appendix: { slides: [...mockEnvelope.deck!.appendix.slides, moreSlides] },
        },
      },
    })
    render(<AppendixSection />)
    expect(screen.getByText('2 slides')).toBeInTheDocument()
  })
})
