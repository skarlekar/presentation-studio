import '@testing-library/jest-dom'
import { vi } from 'vitest'

// @testing-library/react v16 automatically calls cleanup() after each test
// in vitest — no manual afterEach needed.

// Mock fetch globally
;(globalThis as any).fetch = vi.fn()

// Mock import.meta.env
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_BASE_URL: 'http://localhost:8001',
    VITE_APP_NAME: 'DeckForge AI',
    VITE_POLL_INTERVAL_MS: '2000',
  },
})
