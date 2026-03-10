/**
 * JsonPreview component tests.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import JsonPreview from '@/components/JsonPreview'

describe('JsonPreview', () => {
  it('renders a pre element with aria-label', () => {
    render(<JsonPreview data={{ key: 'value' }} />)
    expect(screen.getByLabelText('Deck JSON preview')).toBeInTheDocument()
  })

  it('renders string values from the data', () => {
    render(<JsonPreview data={{ hello: 'world' }} />)
    expect(screen.getByText(/"hello"/)).toBeInTheDocument()
    expect(screen.getByText(/"world"/)).toBeInTheDocument()
  })

  it('renders numeric values', () => {
    render(<JsonPreview data={{ count: 42 }} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders boolean values', () => {
    render(<JsonPreview data={{ active: true, done: false }} />)
    expect(screen.getByText('true')).toBeInTheDocument()
    expect(screen.getByText('false')).toBeInTheDocument()
  })

  it('shows truncation notice when maxLines exceeded', () => {
    // Create data that generates > 5 lines of JSON
    const bigData = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`key${i}`, `value${i}`]))
    render(<JsonPreview data={bigData} maxLines={5} />)
    expect(screen.getByText(/Showing first 5/)).toBeInTheDocument()
  })

  it('does not show truncation when within maxLines', () => {
    render(<JsonPreview data={{ a: 1 }} maxLines={100} />)
    expect(screen.queryByText(/Showing first/)).not.toBeInTheDocument()
  })
})
