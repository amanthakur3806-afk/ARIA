import { useState } from 'react'
import { AppShell } from './components/layout/AppShell'
import { ChatPage } from './features/chat/ChatPage'

function App() {
  const [isRagModalOpen, setIsRagModalOpen] = useState(false)

  return (
    <AppShell onOpenIngest={() => setIsRagModalOpen(true)}>
      <ChatPage
        isRagModalOpen={isRagModalOpen}
        setIsRagModalOpen={setIsRagModalOpen}
      />
    </AppShell>
  )
}

export default App
