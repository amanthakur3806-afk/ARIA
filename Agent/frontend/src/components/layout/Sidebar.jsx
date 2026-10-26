import { Brand } from './Brand'
import { Icon } from '../ui/Icon'
import './Sidebar.css'

const navItems = [
  { label: 'Study chat', icon: 'chat', active: true },
  { label: 'My library', icon: 'book' },
  { label: 'Study tasks', icon: 'tasks' },
]

export function Sidebar({ isOpen, onClose, onNewChat }) {
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
        {navItems.map((item) => (
          <button
            aria-current={item.active ? 'page' : undefined}
            className={`nav-item${item.active ? ' nav-item--active' : ''}`}
            disabled={!item.active}
            key={item.label}
            onClick={onClose}
            title={item.active ? 'Current page' : 'Coming soon'}
            type="button"
          >
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
            {!item.active && <span className="nav-item__soon">Soon</span>}
          </button>
        ))}
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
