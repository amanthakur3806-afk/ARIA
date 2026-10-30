import { Icon } from '../../components/ui/Icon'
import './WelcomePanel.css'

const suggestions = [
  { icon: 'book', label: 'Explain a tricky concept', prompt: 'Explain Virtual Memory and Paging mechanisms in simple terms' },
  { icon: 'document', label: 'Generate study flashcards', prompt: 'Generate 4 flashcards from my notes on Processes and Threads' },
  { icon: 'tasks', label: 'Make a revision plan & quiz', prompt: 'Create a 45-minute revision plan and 5 quiz questions for Operating Systems' },
  { icon: 'sparkle', label: 'Generate an architecture flowchart', prompt: 'Create a step-by-step flowchart for RAG explaining how it works and what happens when' },
]

export function WelcomePanel({ onSelectSuggestion }) {
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
        Ask questions, revise concepts, and generate active-recall flashcards & quizzes.<br className="welcome__desktop-break" />
        Connected with RAG and FastMCP study tools.
      </p>

      <div aria-label="Try asking" className="suggestion-list">
        {suggestions.map((suggestion) => (
          <button
            className="suggestion-card"
            key={suggestion.label}
            type="button"
            title={suggestion.prompt}
            onClick={() => onSelectSuggestion && onSelectSuggestion(suggestion.prompt)}
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
