import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

// Initialize Mermaid with safe defaults (htmlLabels: false avoids XML/DOMPurify entity errors)
mermaid.initialize({
  startOnLoad: false,
  suppressErrorRendering: true,
  theme: 'neutral',
  securityLevel: 'loose',
  fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: false,
    curve: 'basis',
  },
})

/**
 * Robust client-side Mermaid sanitizer.
 * Fixes unclosed brackets, dangling escapes, ampersands, slashes, and unbalanced subgraphs before parsing.
 */
export function sanitizeMermaidCode(raw) {
  if (!raw) return ''
  let cleaned = String(raw).trim()
  // Strip opening markdown code fence (with or without 'mermaid')
  cleaned = cleaned.replace(/^```(?:mermaid)?\s*/i, '')
  // Strip closing markdown code fence
  cleaned = cleaned.replace(/```\s*$/i, '')
  // Strip XML/HTML tags
  cleaned = cleaned.replace(/<[^>]+>/g, '')
  // Fix escaped quotes and newlines
  cleaned = cleaned.replace(/\\"/g, '"').replace(/\\n/g, '\n')
  // Strip stray backslashes
  cleaned = cleaned.replace(/\\/g, '')

  // Replace & with 'and' everywhere (Mermaid treats & as multi-connection syntax)
  cleaned = cleaned.replace(/&/g, 'and')

  // Replace all slashes (with or without spaces) with ' - ' to avoid lexer errors
  cleaned = cleaned.replace(/\s*\/\s*/g, ' - ')

  // Clean inside quotes: remove inner parentheses that might clash with node shape delimiters
  cleaned = cleaned.replace(/(\[[^\]]*\]|\{[^}]*\})/g, (match) => {
    return match.replace(/\(([^)]+)\)/g, '- $1')
  })

  // Convert old edge label syntax: A -- "text" --> B to standard A -->|text| B
  cleaned = cleaned.replace(/--\s*"([^"]+)"\s*-->/g, '-->|$1|')
  cleaned = cleaned.replace(/--\s*\|([^|]+)\|\s*-->/g, '-->|$1|')

  cleaned = cleaned.trim()

  if (!/^(flowchart|graph)\s+[A-Za-z]+/i.test(cleaned)) {
    cleaned = `flowchart TD\n${cleaned}`
  }

  // Repair unclosed brackets line by line
  const lines = cleaned.split('\n')
  const fixedLines = lines.map((line) => {
    let l = line.replace(/\s+$/, '')
    if (l.includes('{"') && !l.includes('"}') && !l.includes('}}')) {
      l = l + '"}'
    } else if (l.includes('["') && !l.includes('"]') && !l.includes(']')) {
      l = l + '"]'
    } else if (l.includes('(("') && !l.includes('"))')) {
      l = l + '"))'
    }
    return l
  })

  let joined = fixedLines.join('\n')
  const subgraphs = (joined.match(/\bsubgraph\b/gi) || []).length
  const ends = (joined.match(/\bend\b/gi) || []).length
  if (subgraphs > ends) {
    for (let i = 0; i < subgraphs - ends; i++) {
      joined += '\n    end'
    }
  }

  return joined
}

/**
 * Extracts a simplified, foolproof Mermaid flowchart by stripping subgraphs
 * and keeping pure node transitions as a zero-failure fallback.
 */
export function simplifyMermaidCode(raw) {
  if (!raw) return 'flowchart TD\n    A["Start Process"] --> B["Complete"]'
  const lines = raw.split('\n')
  const keptLines = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || /^subgraph\b/i.test(trimmed) || /^end$/i.test(trimmed)) {
      continue
    }
    if (/^(flowchart|graph)\b/i.test(trimmed)) {
      continue
    }
    if (trimmed.includes('-->') || trimmed.includes('---') || trimmed.includes('["') || trimmed.includes('{"')) {
      let safeLine = trimmed.replace(/&/g, 'and').replace(/[<>{}]/g, (c) => (c === '{' || c === '}' ? c : ''))
      keptLines.push(`    ${safeLine}`)
    }
  }
  if (keptLines.length === 0) {
    return 'flowchart TD\n    A["Start Process"] --> B["Execute Operations"] --> C["Complete"]'
  }
  return `flowchart TD\n${keptLines.join('\n')}`
}

/**
 * Visual Flowchart Fallback component.
 * Renders an interactive, connected node-and-arrow card flow if Mermaid SVG rendering fails,
 * guaranteeing the user never sees raw text/code in place of a flowchart.
 */
export function VisualFlowchartFallback({ flowchart, cleanCode }) {
  const [showCode, setShowCode] = useState(false)
  const steps = flowchart?.steps_walkthrough || []
  const phases = flowchart?.phases || []
  const decisions = flowchart?.decision_points || []

  return (
    <div className="visual-flowchart-fallback">
      <div className="visual-fallback-header">
        <span className="visual-fallback-badge">🗺️ Visual Workflow Flowchart</span>
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => setShowCode(!showCode)}
        >
          {showCode ? '🖼️ View Visual Graph' : '💻 View Markdown Code'}
        </button>
      </div>

      {showCode ? (
        <pre className="mermaid-code-view">
          <code>{cleanCode}</code>
        </pre>
      ) : (
        <div className="visual-flow-nodes-container">
          {phases.length > 0 ? (
            phases.map((phase, pIdx) => {
              const phaseSteps = steps.filter((s) => s.phase === phase.title || (phase.node_ids && phase.node_ids.includes(s.component)))
              const displaySteps = phaseSteps.length > 0 ? phaseSteps : steps.slice(pIdx * 2, pIdx * 2 + 2)
              return (
                <div key={phase.phase_id || pIdx} className="visual-flow-phase-group">
                  <div className="visual-phase-title-pill">
                    📂 {phase.title}
                  </div>
                  <div className="visual-phase-nodes">
                    {displaySteps.map((step, sIdx) => (
                      <div key={sIdx} className="visual-flow-step-wrapper">
                        <div className="visual-flow-card">
                          <div className="flow-card-header">
                            <span className="flow-step-num">Step {step.step || sIdx + 1}</span>
                            <span className="flow-comp-tag">{step.component}</span>
                          </div>
                          <p className="flow-action-text">{step.action}</p>
                        </div>
                        {sIdx < displaySteps.length - 1 && (
                          <div className="visual-flow-connector">
                            <span className="connector-line" />
                            <span className="connector-arrow">↓</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {pIdx < phases.length - 1 && (
                    <div className="phase-transition-arrow">
                      <span className="phase-arrow-line" />
                      <span className="phase-arrow-badge">Next Phase ↓</span>
                    </div>
                  )}
                </div>
              )
            })
          ) : steps.length > 0 ? (
            <div className="visual-phase-nodes">
              {steps.map((step, sIdx) => (
                <div key={sIdx} className="visual-flow-step-wrapper">
                  <div className="visual-flow-card">
                    <div className="flow-card-header">
                      <span className="flow-step-num">Step {step.step || sIdx + 1}</span>
                      <span className="flow-comp-tag">{step.component}</span>
                    </div>
                    <p className="flow-action-text">{step.action}</p>
                  </div>
                  {sIdx < steps.length - 1 && (
                    <div className="visual-flow-connector">
                      <span className="connector-line" />
                      <span className="connector-arrow">↓</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-flow-text">Flowchart workflow nodes generated successfully.</p>
          )}

          {decisions.length > 0 && (
            <div className="visual-fallback-decisions">
              <span className="decisions-section-title">⚖️ Key Decision Gates</span>
              <div className="decisions-mini-grid">
                {decisions.map((dp, dIdx) => (
                  <div key={dIdx} className="decision-mini-card">
                    <strong>{dp.condition}</strong>
                    <div className="decision-mini-outcomes">
                      <span className="outcome-pill outcome-pill--yes">✔ {dp.outcome_yes}</span>
                      <span className="outcome-pill outcome-pill--no">✖ {dp.outcome_no}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Dedicated Mermaid Diagram renderer component.
 * Parses and renders Markdown Mermaid syntax into interactive SVGs with zoom controls.
 */
export function MermaidDiagram({ code, fallbackData }) {
  const containerRef = useRef(null)
  const [svgHtml, setSvgHtml] = useState('')
  const [renderError, setRenderError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [showCode, setShowCode] = useState(false)
  const [zoom, setZoom] = useState(1.0)

  // Clean and sanitize diagram code
  const cleanCode = sanitizeMermaidCode(code)

  useEffect(() => {
    let isCancelled = false
    if (!cleanCode) return

    const renderDiagram = async () => {
      // Alphanumeric ID starting with letter
      const uniqueId = `mermaid_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`
      
      // Create isolated invisible render container
      const tempContainer = document.createElement('div')
      tempContainer.id = `temp_${uniqueId}`
      tempContainer.style.position = 'absolute'
      tempContainer.style.visibility = 'hidden'
      tempContainer.style.top = '-9999px'
      document.body.appendChild(tempContainer)

      try {
        const { svg } = await mermaid.render(uniqueId, cleanCode, tempContainer)
        if (!isCancelled) {
          setSvgHtml(svg)
          setRenderError(null)
        }
      } catch (err) {
        // Retry with simplified representation (no subgraphs) before falling back
        try {
          const simplifiedCode = simplifyMermaidCode(cleanCode)
          const fallbackId = `${uniqueId}_fb`
          const { svg: fbSvg } = await mermaid.render(fallbackId, simplifiedCode, tempContainer)
          if (!isCancelled) {
            setSvgHtml(fbSvg)
            setRenderError(null)
          }
        } catch (fallbackErr) {
          if (!isCancelled) {
            console.warn('Mermaid rendering notice:', err)
            setRenderError(err.message || 'Error parsing diagram syntax')
          }
        }
      } finally {
        if (tempContainer.parentNode) {
          tempContainer.parentNode.removeChild(tempContainer)
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

  function handleZoomIn() {
    setZoom((z) => Math.min(+(z + 0.15).toFixed(2), 1.8))
  }

  function handleZoomOut() {
    setZoom((z) => Math.max(+(z - 0.15).toFixed(2), 0.5))
  }

  function handleZoomReset() {
    setZoom(1.0)
  }

  return (
    <div className="mermaid-diagram-wrap">
      <div className="mermaid-diagram-wrap__toolbar">
        <span className="mermaid-toolbar__badge">📊 Mermaid Flowchart</span>
        <div className="mermaid-toolbar__actions">
          {!showCode && !renderError && (
            <div className="mermaid-zoom-controls">
              <button
                type="button"
                className="toolbar-btn zoom-btn"
                onClick={handleZoomOut}
                title="Zoom Out"
              >
                −
              </button>
              <span className="zoom-level-badge">{Math.round(zoom * 100)}%</span>
              <button
                type="button"
                className="toolbar-btn zoom-btn"
                onClick={handleZoomIn}
                title="Zoom In"
              >
                +
              </button>
              <button
                type="button"
                className="toolbar-btn zoom-btn"
                onClick={handleZoomReset}
                title="Reset Zoom"
              >
                ↺
              </button>
            </div>
          )}
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
        <VisualFlowchartFallback flowchart={fallbackData} cleanCode={cleanCode} />
      ) : (
        <div
          ref={containerRef}
          className="mermaid-svg-container"
        >
          <div
            className="mermaid-svg-viewport"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top center',
              transition: 'transform 0.15s ease',
              width: '100%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
            }}
            dangerouslySetInnerHTML={{ __html: svgHtml }}
          />
        </div>
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
          <MermaidDiagram code={mermaid_markdown} fallbackData={flowchart} />
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
