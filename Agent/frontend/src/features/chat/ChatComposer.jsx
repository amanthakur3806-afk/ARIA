import { Icon } from '../../components/ui/Icon'
import './ChatComposer.css'

export function ChatComposer() {
  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          aria-label="Message ARYA"
          maxLength={4000}
          disabled
          placeholder="Ask anything about what you're learning..."
          rows={1}
        />
        <div className="composer__bottom">
          <span className="composer__hint">Thoughtful answers start with a question</span>
          <div className="composer__actions">
            <span className="composer__shortcut">Shift + Enter for a new line</span>
            <button
              aria-label="Send message (not implemented)"
              className="composer__send"
              disabled
              type="button"
            >
              <Icon name="send" size={16} />
            </button>
          </div>
        </div>
      </div>
      <p className="composer-wrap__disclaimer">ARYA can make mistakes. Check important information.</p>
    </div>
  )
}
