'use client'

import { useState } from 'react'

// Tiny client-only button that copies `text` to the clipboard and gives a
// 1.5-second "Copied!" affordance. The "use client" boundary stays small —
// only this button is hydrated, not the parent.
export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API requires a secure context (https or localhost) and
      // user activation. If it fails, fall back to letting the user select.
      alert('Copy failed — select the text manually.')
    }
  }

  return (
    <button
      onClick={handleCopy}
      style={{
        padding: '4px 10px',
        fontSize: 12,
        fontWeight: 500,
        borderRadius: 6,
        background: copied ? 'rgba(48, 209, 88, 0.15)' : 'rgba(255, 255, 255, 0.06)',
        color: copied ? 'var(--success)' : 'var(--text-dim)',
        border: `1px solid ${copied ? 'rgba(48, 209, 88, 0.3)' : 'var(--border)'}`,
        transition: 'all 0.15s ease',
      }}
    >
      {copied ? '✓ Copied' : label}
    </button>
  )
}
