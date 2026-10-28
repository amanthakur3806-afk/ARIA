import { useRef, useState } from 'react'
import { Icon } from '../../components/ui/Icon'
import './ChatComposer.css'

export function ChatComposer({ onSend, onOpenIngest, isLoading = false, placeholder }) {
  const [text, setText] = useState('')
  const fileInputRef = useRef(null)

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
          <div className="composer__left-actions">
            <button
              type="button"
              aria-label="Attach a study file"
              className="composer__attach-btn"
              disabled={isLoading}
              onClick={() => fileInputRef.current?.click()}
              title="Attach a study file"
            >
              <Icon name="plus" size={18} />
              <span>Add file</span>
            </button>
            <input
              ref={fileInputRef}
              accept=".txt,.md,.json,.csv,.pdf"
              aria-label="Choose a study file"
              className="composer__file-input"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) onOpenIngest(file)
                event.target.value = ''
              }}
              type="file"
            />
            <span className="composer__hint">Powered by User-Scoped RAG & FastMCP</span>
          </div>
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
      <p className="composer-wrap__disclaimer">ARIA provides AI revision assistance. Ingest your course notes to enable grounded answers.</p>
    </form>
  )
}
