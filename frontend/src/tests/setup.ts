import '@testing-library/jest-dom'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock fetch globally
(globalThis as any).fetch = vi.fn()

// Mock import.meta.env
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: 'http://localhost:8001',
    VITE_APP_NAME: 'DeckForge AI',
    VITE_POLL_INTERVAL_MS: '2000',
  },
})
