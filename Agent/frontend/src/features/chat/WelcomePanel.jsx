import { Icon } from '../../components/ui/Icon'
import './WelcomePanel.css'

const suggestions = [
  { icon: 'book', label: 'Explain a tricky concept', prompt: 'Explain a tricky concept in simple terms' },
  { icon: 'document', label: 'Summarize my notes', prompt: 'Help me summarize my study notes' },
  { icon: 'tasks', label: 'Make a study plan', prompt: 'Help me make a study plan for this week' },
]

export function WelcomePanel() {
  return (
    <section aria-labelledby="welcome-title" className="welcome">
      <div className="welcome__illustration" aria-hidden="true">
        <div className="welcome__orbit welcome__orbit--outer" />
        <div className="welcome__orbit welcome__orbit--inner" />
        <div className="welcome__book">
          <span />
          <span />
          <span />
        </div>
        <span className="welcome__sparkle welcome__sparkle--one"><Icon name="sparkle" size={19} /></span>
        <span className="welcome__sparkle welcome__sparkle--two"><Icon name="sparkle" size={13} /></span>
      </div>
      <div className="welcome__eyebrow"><span /> YOUR STUDY SPACE</div>
      <h1 id="welcome-title">A little clarity goes<br />a long way.</h1>
      <p className="welcome__description">
        Bring your questions, notes, and big ideas.<br className="welcome__desktop-break" />
        We&apos;ll work through them together.
      </p>
      <div aria-label="Try asking" className="suggestion-list">
        {suggestions.map((suggestion) => (
          <button
            className="suggestion-card"
            disabled
            key={suggestion.label}
            type="button"
            title={suggestion.prompt}
          >
            <span className="suggestion-card__icon"><Icon name={suggestion.icon} size={17} /></span>
            <span>{suggestion.label}</span>
            <Icon className="suggestion-card__arrow" name="chevron" size={15} />
          </button>
        ))}
      </div>
    </section>
  )
}
