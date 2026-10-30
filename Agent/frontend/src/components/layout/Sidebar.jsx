import { Brand } from './Brand'
import { Icon } from '../ui/Icon'
import './Sidebar.css'

export function Sidebar({
  isOpen,
  onClose,
  onNewChat,
  onOpenIngest,
  onOpenLibrary,
  threads = [],
  activeSessionId,
  onSelectThread,
  onDeleteThread,
}) {
  return (
    <aside aria-label="Main navigation" className={`sidebar${isOpen ? ' sidebar--open' : ''}`}>
      <div className="sidebar__top">
        <Brand />
        <button
          aria-label="Close navigation"
          className="icon-button sidebar__close"
          onClick={onClose}
          type="button"
        >
          <Icon name="close" />
        </button>
      </div>

      <button className="new-chat-button" onClick={onNewChat} type="button">
        <Icon name="plus" size={18} />
        <span>New study chat</span>
        <span aria-hidden="true" className="new-chat-button__shortcut">⌘ K</span>
      </button>

      <div className="sidebar__section-label">Workspace</div>
      <nav className="sidebar__nav">
        <button
          aria-current="page"
          className="nav-item nav-item--active"
          onClick={onClose}
          type="button"
        >
          <Icon name="chat" size={18} />
          <span>Study chat</span>
        </button>

        {/* My Library opens the Library view of the modal */}
        <button
          className="nav-item"
          onClick={() => {
            onClose()
            if (onOpenLibrary) onOpenLibrary()
            else if (onOpenIngest) onOpenIngest()
          }}
          title="Open study library and ingested course materials"
          type="button"
        >
          <Icon name="book" size={18} />
          <span>My library</span>
          <span className="nav-item__soon" style={{ background: 'var(--color-green, #456b55)', color: '#fff' }}>RAG</span>
        </button>
      </nav>

      <div className="sidebar__section-label sidebar__section-label--recent">Recent</div>
      <div className="recent-chat-list">
        {threads.length === 0 ? (
          <p className="recent-chat-empty">No conversations yet.</p>
        ) : (
          threads.map((thread) => {
            const isActive = thread.id === activeSessionId
            return (
              <div
                key={thread.id}
                className={`recent-chat-item ${isActive ? 'recent-chat-item--active' : ''}`}
                onClick={() => {
                  if (onSelectThread) onSelectThread(thread.id)
                  if (onClose) onClose()
                }}
                role="button"
                tabIndex={0}
              >
                <span className="recent-chat-item__icon">💬</span>
                <span className="recent-chat-item__title" title={thread.title || thread.id}>
                  {thread.title || thread.id}
                </span>
                <button
                  className="recent-chat-item__del"
                  onClick={(e) => onDeleteThread && onDeleteThread(thread.id, e)}
                  title="Delete conversation"
                  type="button"
                >
                  ✕
                </button>
              </div>
            )
          })
        )}
      </div>

      <div className="sidebar__footer">
        <div className="sidebar__status-badge">
          <span className="status-dot status-dot--online" />
          <span>PostgreSQL · FastMCP</span>
        </div>
      </div>
    </aside>
  )
}
