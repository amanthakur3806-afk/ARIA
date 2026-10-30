import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useTheme } from '../theme/useTheme'
import './AppShell.css'

export function AppShell({
  children,
  onOpenIngest,
  onOpenLibrary,
  threads = [],
  activeSessionId,
  onSelectThread,
  onNewChat,
  onDeleteThread,
}) {
  const { theme, toggleTheme } = useTheme()
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const [notice, setNotice] = useState('')

  function handleNewChat() {
    setIsNavigationOpen(false)
    setNotice('')
    if (onNewChat) {
      onNewChat()
    }
  }

  return (
    <div className="app-shell">
      {isNavigationOpen && (
        <button
          aria-label="Close navigation"
          className="sidebar-backdrop"
          onClick={() => setIsNavigationOpen(false)}
          type="button"
        />
      )}
      <Sidebar
        activeSessionId={activeSessionId}
        isOpen={isNavigationOpen}
        onClose={() => setIsNavigationOpen(false)}
        onDeleteThread={onDeleteThread}
        onNewChat={handleNewChat}
        onOpenIngest={onOpenIngest}
        onOpenLibrary={onOpenLibrary}
        onSelectThread={onSelectThread}
        threads={threads}
      />
      <div className="app-shell__main">
        <TopBar
          onMenuClick={() => setIsNavigationOpen(true)}
          onThemeToggle={toggleTheme}
          onOpenIngest={onOpenIngest}
          theme={theme}
        />
        {notice && (
          <div className="app-shell__notice" role="status">
            <span>{notice}</span>
            <button aria-label="Dismiss notice" onClick={() => setNotice('')} type="button">×</button>
          </div>
        )}
        <main className="app-shell__content">{children}</main>
      </div>
    </div>
  )
}
