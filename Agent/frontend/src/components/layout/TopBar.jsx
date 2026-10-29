import { Icon } from '../ui/Icon'
import './TopBar.css'

export function TopBar({ onMenuClick, onThemeToggle, onOpenIngest, theme }) {
  return (
    <header className="topbar">
      <button
        aria-label="Open navigation"
        className="icon-button topbar__menu"
        onClick={onMenuClick}
        type="button"
      >
        <Icon name="menu" />
      </button>
      <div className="topbar__breadcrumbs">
        <span>Workspace</span>
        <Icon name="chevron" size={14} />
        <strong>Study chat</strong>
      </div>
      <div className="topbar__actions">
        {/* Prominent Ingest Notes Button in Top Header */}
        <button
          className="topbar__ingest-btn"
          onClick={onOpenIngest}
          title="Upload data file or ingest notes into knowledge base"
          type="button"
        >
          <span className="topbar__ingest-icon">📥</span>
          <span>Upload / Ingest Notes</span>
        </button>

        <button
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          aria-pressed={theme === 'dark'}
          className="theme-toggle"
          onClick={onThemeToggle}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          type="button"
        >
          <Icon name={theme === 'light' ? 'moon' : 'sun'} size={17} />
          <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
        </button>
        <div className="preview-status">
          RAG Active
        </div>
      </div>
    </header>
  )
}
