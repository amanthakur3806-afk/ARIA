import { useState } from 'react'
import { Icon } from '../../components/ui/Icon'
import './ChatComposer.css'

export function ChatComposer({ onSend, isLoading = false, placeholder }) {
  const [text, setText] = useState('')

  function handleSubmit(e) {
    if (e) e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <form className="composer-wrap" onSubmit={handleSubmit}>
      <div className="composer">
        <textarea
          aria-label="Message ARIA"
          maxLength={4000}
          disabled={isLoading}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Ask ARIA anything: explain a concept, make flashcards, or create a quiz..."}
          rows={Math.min(5, Math.max(1, text.split('\n').length))}
        />
        <div className="composer__bottom">
          <span className="composer__hint">Powered by RAG & FastMCP Tools</span>
          <div className="composer__actions">
            <span className="composer__shortcut">Shift + Enter for a new line</span>
            <button
              aria-label="Send message"
              className="composer__send"
              disabled={!text.trim() || isLoading}
              type="submit"
            >
              {isLoading ? (
                <div className="composer__spinner" />
              ) : (
                <Icon name="send" size={16} />
              )}
            </button>
          </div>
        </div>
      </div>
      <p className="composer-wrap__disclaimer">ARIA provides AI revision assistance. Always cross-verify critical exam concepts.</p>
    </form>
  )
}
