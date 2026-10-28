import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useTheme } from '../theme/useTheme'
import './AppShell.css'

export function AppShell({ children, onOpenIngest }) {
  const { theme, toggleTheme } = useTheme()
  const [isNavigationOpen, setIsNavigationOpen] = useState(false)
  const [notice, setNotice] = useState('')

  function handleNewChat() {
    setIsNavigationOpen(false)
    setNotice('')
    window.location.reload()
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
        isOpen={isNavigationOpen}
        onClose={() => setIsNavigationOpen(false)}
        onNewChat={handleNewChat}
        onOpenIngest={onOpenIngest}
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
