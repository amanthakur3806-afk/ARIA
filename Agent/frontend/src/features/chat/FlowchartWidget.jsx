import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

// Initialize Mermaid with safe defaults
mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis',
  },
})

/**
 * Dedicated Mermaid Diagram renderer component.
 * Parses and renders Markdown Mermaid syntax into interactive SVGs.
 */
export function MermaidDiagram({ code }) {
  const containerRef = useRef(null)
  const [svgHtml, setSvgHtml] = useState('')
  const [renderError, setRenderError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [showCode, setShowCode] = useState(false)

  // Clean code from markdown code fences
  const cleanCode = (code || '')
    .replace(/^```mermaid\s*/i, '')
    .replace(/```\s*$/, '')
    .trim()

  useEffect(() => {
    let isCancelled = false
    if (!cleanCode) return

    const renderDiagram = async () => {
      const uniqueId = `mermaid_${Math.random().toString(36).substring(2, 10)}`
      try {
        const { svg } = await mermaid.render(uniqueId, cleanCode)
        if (!isCancelled) {
          setSvgHtml(svg)
          setRenderError(null)
        }
      } catch (err) {
        if (!isCancelled) {
          console.warn('Mermaid rendering notice:', err)
          setRenderError(err.message || 'Error parsing diagram syntax')
        }
      }
    }

    renderDiagram()

    return () => {
      isCancelled = true
    }
  }, [cleanCode])

  function handleCopy() {
    navigator.clipboard.writeText(`\`\`\`mermaid\n${cleanCode}\n\`\`\``)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="mermaid-diagram-wrap">
      <div className="mermaid-diagram-wrap__toolbar">
        <span className="mermaid-toolbar__badge">📊 Mermaid Flowchart</span>
        <div className="mermaid-toolbar__actions">
          <button
            type="button"
            className="toolbar-btn"
            onClick={() => setShowCode(!showCode)}
            title="Toggle between SVG diagram and Markdown code"
          >
            {showCode ? '🖼️ View Diagram' : '💻 View Code'}
          </button>
          <button
            type="button"
            className="toolbar-btn"
            onClick={handleCopy}
            title="Copy Mermaid Markdown syntax"
          >
            {copied ? '✅ Copied' : '📋 Copy Markdown'}
          </button>
        </div>
      </div>

      {showCode ? (
        <pre className="mermaid-code-view">
          <code>{cleanCode}</code>
        </pre>
      ) : renderError ? (
        <div className="mermaid-error-fallback">
          <p className="mermaid-error-text">⚠️ <em>Diagram rendered in text mode:</em></p>
          <pre className="mermaid-code-view">
            <code>{cleanCode}</code>
          </pre>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="mermaid-svg-container"
          dangerouslySetInnerHTML={{ __html: svgHtml }}
        />
      )}
    </div>
  )
}

/**
 * Interactive Flowchart Widget.
 * Displays title, visual diagram, step-by-step "what happens when" progression,
 * key components, and decision logic branches.
 */
export function FlowchartWidget({ flowchart }) {
  const [activeTab, setActiveTab] = useState('diagram') // 'diagram' | 'walkthrough' | 'components' | 'decisions'

  if (!flowchart) return null

  const {
    title = 'Process Flowchart',
    mermaid_markdown = '',
    steps_walkthrough = [],
    components = [],
    decision_points = [],
  } = flowchart

  return (
    <div className="flowchart-widget">
      <div className="flowchart-widget__header">
        <div className="flowchart-title-area">
          <span className="flowchart-badge">🗺️ Interactive Workflow</span>
          <h3 className="flowchart-title">{title}</h3>
        </div>
      </div>

      {/* Tabs */}
      <div className="flowchart-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'diagram'}
          className={`flowchart-tab-btn ${activeTab === 'diagram' ? 'flowchart-tab-btn--active' : ''}`}
          onClick={() => setActiveTab('diagram')}
        >
          📊 Flowchart Diagram
        </button>
        {steps_walkthrough.length > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'walkthrough'}
            className={`flowchart-tab-btn ${activeTab === 'walkthrough' ? 'flowchart-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('walkthrough')}
          >
            🔍 Step Walkthrough ({steps_walkthrough.length})
          </button>
        )}
        {components.length > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'components'}
            className={`flowchart-tab-btn ${activeTab === 'components' ? 'flowchart-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('components')}
          >
            ⚙️ Components ({components.length})
          </button>
        )}
        {decision_points.length > 0 && (
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'decisions'}
            className={`flowchart-tab-btn ${activeTab === 'decisions' ? 'flowchart-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('decisions')}
          >
            ⚖️ Decisions ({decision_points.length})
          </button>
        )}
      </div>

      {/* Tab Panels */}
      <div className="flowchart-tab-content">
        {activeTab === 'diagram' && (
          <MermaidDiagram code={mermaid_markdown} />
        )}

        {activeTab === 'walkthrough' && (
          <div className="walkthrough-timeline">
            {steps_walkthrough.map((stepItem, idx) => (
              <div key={idx} className="walkthrough-step-card">
                <div className="step-number-bubble">{stepItem.step || idx + 1}</div>
                <div className="step-info">
                  <div className="step-header">
                    <span className="step-phase-pill">{stepItem.phase || 'Stage'}</span>
                    <span className="step-component-title">{stepItem.component}</span>
                  </div>
                  <p className="step-action-desc">{stepItem.action}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'components' && (
          <div className="components-grid">
            {components.map((comp, idx) => (
              <div key={idx} className="component-card">
                <div className="component-card__header">
                  <span className="component-name">{comp.name}</span>
                  <span className="component-role">{comp.role}</span>
                </div>
                <p className="component-details">{comp.details}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'decisions' && (
          <div className="decisions-list">
            {decision_points.map((dp, idx) => (
              <div key={idx} className="decision-card">
                <div className="decision-card__condition">
                  <span className="condition-label">Condition:</span>
                  <strong>{dp.condition}</strong>
                </div>
                <div className="decision-branches">
                  <div className="decision-branch decision-branch--yes">
                    <span className="branch-tag">✅ YES / TRUE</span>
                    <p>{dp.outcome_yes}</p>
                  </div>
                  <div className="decision-branch decision-branch--no">
                    <span className="branch-tag">❌ NO / FALSE</span>
                    <p>{dp.outcome_no}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
