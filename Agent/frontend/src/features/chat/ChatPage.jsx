import { ChatComposer } from './ChatComposer'
import { WelcomePanel } from './WelcomePanel'
import './ChatPage.css'

export function ChatPage() {
  return (
    <section aria-label="Study chat" className="chat-page">
      <div className="chat-page__welcome">
        <WelcomePanel />
      </div>
      <div className="chat-page__composer">
        <ChatComposer />
      </div>
    </section>
  )
}
