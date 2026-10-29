import { Brand } from './Brand'
import { Icon } from '../ui/Icon'
import './Sidebar.css'

export function Sidebar({ isOpen, onClose, onNewChat, onOpenIngest }) {
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

        {/* My Library is active and opens the Ingest / Knowledge Base modal */}
        <button
          className="nav-item"
          onClick={() => {
            onClose()
            if (onOpenIngest) onOpenIngest()
          }}
          title="Open knowledge base and ingested documents"
          type="button"
        >
          <Icon name="book" size={18} />
          <span>My library</span>
          <span className="nav-item__soon" style={{ background: '#6366f1', color: '#fff' }}>RAG</span>
        </button>

      </nav>

      <div className="sidebar__section-label sidebar__section-label--recent">Recent</div>
      <div className="recent-chat-list">
        <p className="recent-chat-empty">Conversations will appear here.</p>
      </div>

      <div className="sidebar__footer">
        <div aria-hidden="true" className="profile-avatar">S</div>
        <div className="sidebar__profile-copy">
          <span className="sidebar__profile-name">Study space</span>
          <span className="sidebar__profile-plan">Personal workspace</span>
        </div>
        <button
          aria-label="Workspace options (coming soon)"
          className="icon-button sidebar__more"
          disabled
          type="button"
        >
          ···
        </button>
      </div>
    </aside>
  )
}
