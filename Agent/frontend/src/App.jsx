import { useEffect, useState } from 'react'
import { AppShell } from './components/layout/AppShell'
import { ChatPage } from './features/chat/ChatPage'

function App() {
  const [isRagModalOpen, setIsRagModalOpen] = useState(false)
  const [ragModalTab, setRagModalTab] = useState('library')
  const [userId] = useState('student-1')
  const [threads, setThreads] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(() => {
    return localStorage.getItem('aria_active_thread') || 'thread-1'
  })

  async function loadThreads() {
    try {
      const res = await fetch(`/api/v1/chat/threads?user_id=${encodeURIComponent(userId)}`)
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data.threads)) {
          setThreads(data.threads)
        }
      }
    } catch (e) {
      console.warn('Failed to load threads:', e)
    }
  }

  useEffect(() => {
    loadThreads()
  }, [userId])

  function handleSelectThread(threadId) {
    setActiveSessionId(threadId)
    localStorage.setItem('aria_active_thread', threadId)
  }

  function handleNewChat() {
    const newId = `thread_${Date.now().toString(36)}`
    setActiveSessionId(newId)
    localStorage.setItem('aria_active_thread', newId)
  }

  async function handleDeleteThread(threadId, e) {
    if (e) e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this conversation?')) return
    try {
      await fetch(`/api/v1/chat/threads/${encodeURIComponent(threadId)}?user_id=${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      })
      const remaining = threads.filter((t) => t.id !== threadId)
      setThreads(remaining)
      if (activeSessionId === threadId) {
        const nextId = remaining.length > 0 ? remaining[0].id : 'thread-1'
        setActiveSessionId(nextId)
        localStorage.setItem('aria_active_thread', nextId)
      }
    } catch (err) {
      console.warn('Failed to delete thread:', err)
    }
  }

  function handleOpenLibrary() {
    setRagModalTab('library')
    setIsRagModalOpen(true)
  }

  function handleOpenIngest() {
    setRagModalTab('ingest')
    setIsRagModalOpen(true)
  }

  return (
    <AppShell
      activeSessionId={activeSessionId}
      onDeleteThread={handleDeleteThread}
      onNewChat={handleNewChat}
      onOpenIngest={handleOpenIngest}
      onOpenLibrary={handleOpenLibrary}
      onSelectThread={handleSelectThread}
      threads={threads}
    >
      <ChatPage
        activeSessionId={activeSessionId}
        initialRagTab={ragModalTab}
        isRagModalOpen={isRagModalOpen}
        onRefreshThreads={loadThreads}
        onSelectSession={handleSelectThread}
        setIsRagModalOpen={setIsRagModalOpen}
        userId={userId}
      />
    </AppShell>
  )
}

export default App
