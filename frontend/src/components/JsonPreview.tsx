/**
 * JsonPreview — syntax-highlighted JSON viewer for the export page.
 * Uses a simple tokenizer (no external library required).
 */
interface Props {
  data: unknown
  maxLines?: number
}

export default function JsonPreview({ data, maxLines = 150 }: Props) {
  const json = JSON.stringify(data, null, 2)
  const lines = json.split('\n')
  const truncated = lines.length > maxLines
  const displayLines = truncated ? lines.slice(0, maxLines) : lines

  return (
    <div className="relative">
      <pre
        className="bg-gray-950 text-gray-100 rounded-xl p-4 text-xs overflow-auto max-h-96 scrollbar-thin"
        aria-label="Deck JSON preview"
      >
        <code>{colorize(displayLines.join('\n'))}</code>
      </pre>
      {truncated && (
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-gray-950 to-transparent rounded-b-xl flex items-end justify-center pb-3">
          <span className="text-xs text-gray-400">
            Showing first {maxLines} of {lines.length} lines
          </span>
        </div>
      )}
    </div>
  )
}

// ── Minimal tokenizer ─────────────────────────────────────────────────────────

function colorize(json: string): React.ReactNode {
  // Simple regex-based colorization — no external dep
  const parts: React.ReactNode[] = []
  const tokenPattern =
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g

  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = tokenPattern.exec(json)) !== null) {
    // Add gap text
    if (match.index > lastIndex) {
      parts.push(json.slice(lastIndex, match.index))
    }

    const token = match[0]
    let color = 'text-green-400'

    if (/^"/.test(token)) {
      if (/:$/.test(token)) {
        color = 'text-blue-300' // key
      } else {
        color = 'text-amber-300' // string value
      }
    } else if (/true|false/.test(token)) {
      color = 'text-purple-400'
    } else if (/null/.test(token)) {
      color = 'text-red-400'
    } else {
      color = 'text-cyan-300' // number
    }

    parts.push(
      <span key={parts.length} className={color}>
        {token}
      </span>,
    )
    lastIndex = match.index + token.length
  }

  // Trailing text
  if (lastIndex < json.length) {
    parts.push(json.slice(lastIndex))
  }

  return <>{parts}</>
}
