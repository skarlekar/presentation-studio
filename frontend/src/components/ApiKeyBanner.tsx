/**
 * ApiKeyBanner — shown when the server has no Anthropic API key configured.
 * Prompts the user to enter their key; stored in sessionStorage for the session.
 */
import { useState } from 'react'
import { useStore } from '@/store'

export default function ApiKeyBanner() {
  const apiKey           = useStore(s => s.apiKey)
  const apiKeyConfigured = useStore(s => s.apiKeyConfigured)
  const apiKeyChecked    = useStore(s => s.apiKeyChecked)
  const setApiKey        = useStore(s => s.setApiKey)
  const clearApiKey      = useStore(s => s.clearApiKey)

  const [draft, setDraft] = useState('')
  const [showKey, setShowKey] = useState(false)

  // Don't render until we've done the health check
  if (!apiKeyChecked) return null

  // Key is pre-configured on server — nothing to show
  if (apiKeyConfigured) return null

  // Key already stored in session
  if (apiKey) {
    return (
      <div className="bg-green-50 border-b border-green-200 px-4 py-2 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-green-800">
          <span>🔑</span>
          <span>Anthropic API key set for this session</span>
          <span className="font-mono text-xs text-green-600">
            {apiKey.slice(0, 8)}…{apiKey.slice(-4)}
          </span>
        </div>
        <button
          onClick={clearApiKey}
          className="text-xs text-green-700 underline hover:no-underline"
        >
          Clear
        </button>
      </div>
    )
  }

  // No key — prompt the user
  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-3">
      <div className="max-w-3xl mx-auto flex items-start gap-3">
        <span className="text-xl shrink-0 mt-0.5">🔑</span>
        <div className="flex-1 space-y-2">
          <p className="text-sm font-semibold text-amber-900">
            Anthropic API key required
          </p>
          <p className="text-xs text-amber-700">
            No API key is configured on the server. Enter your Anthropic API key below
            to use DeckStudio. It's stored only in your browser session and never sent
            to any third party — only to this DeckStudio backend.
          </p>
          <div className="flex gap-2 items-center">
            <div className="relative flex-1 max-w-sm">
              <input
                type={showKey ? 'text' : 'password'}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="sk-ant-api03-…"
                className="w-full border border-amber-300 rounded-lg px-3 py-1.5 text-sm pr-16 focus:outline-none focus:ring-2 focus:ring-amber-400 font-mono bg-white"
                aria-label="Anthropic API key"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && draft.trim().startsWith('sk-')) {
                    setApiKey(draft.trim())
                    setDraft('')
                  }
                }}
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-amber-600 hover:text-amber-800"
                aria-label={showKey ? 'Hide key' : 'Show key'}
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
            <button
              onClick={() => {
                if (draft.trim().startsWith('sk-')) {
                  setApiKey(draft.trim())
                  setDraft('')
                }
              }}
              disabled={!draft.trim().startsWith('sk-')}
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-lg disabled:opacity-40 transition-colors"
            >
              Save
            </button>
          </div>
          {draft && !draft.trim().startsWith('sk-') && (
            <p className="text-xs text-red-600">
              Anthropic keys start with <code className="font-mono">sk-ant-</code>
            </p>
          )}
          <p className="text-xs text-amber-600">
            Get your key at{' '}
            <a
              href="https://console.anthropic.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:no-underline"
            >
              console.anthropic.com
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
