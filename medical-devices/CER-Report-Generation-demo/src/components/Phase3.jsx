import { useState, useEffect } from 'react'
import { HORIZON_ITEMS, HORIZON_QUARTERS } from '../data/cerData'

// ── Horizon Item ──────────────────────────────────────────────────────────────

function HorizonItem({ item }) {
  const [expanded, setExpanded] = useState(false)
  const [watching, setWatching] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div
      className="section"
      style={{ padding: '12px 14px', cursor: 'pointer', opacity: dismissed ? 0 : 1 }}
      onClick={() => setExpanded(e => !e)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <span className={`tag ${item.tagClass}`}>{item.type}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace', flexShrink: 0 }}>{item.timeline}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4, marginBottom: 6 }}>
        {item.title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{item.impact}</div>

      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '0.5px solid var(--border-tertiary)' }}
             onClick={e => e.stopPropagation()}>

          {/* CardioWatch X1-specific detail */}
          <div className="feed-item-section" style={{ marginBottom: 10 }}>
            <div className="feed-item-section-label">WHAT THIS MEANS FOR CARDIOWATCH X1</div>
            <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{item.detail}</p>
          </div>

          {/* Action steps */}
          <div className="feed-item-section" style={{ marginBottom: 12 }}>
            <div className="feed-item-section-label">RECOMMENDED STEPS</div>
            <ol style={{ margin: 0, paddingLeft: 18 }}>
              {item.steps.map((step, i) => (
                <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{step}</li>
              ))}
            </ol>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className={`btn${watching ? ' btn-primary' : ''}`}
              style={{ fontSize: 12, padding: '6px 12px' }}
              onClick={() => setWatching(w => !w)}
            >
              {watching ? '✓ Watching' : 'Add to Watch List'}
            </button>
            <button
              className="btn"
              style={{ fontSize: 12, padding: '6px 12px', color: 'var(--text-tertiary)' }}
              onClick={() => setDismissed(true)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function Phase3() {
  const [items, setItems]           = useState(HORIZON_ITEMS)
  const [liveSource, setLiveSource] = useState(null)
  const [loadingLive, setLoadingLive] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/data/regulatory_horizon.json')
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json() })
      .then(data => {
        if (!cancelled && data.items?.length) {
          setItems(data.items)
          setLiveSource({ generated_at: data.generated_at, window_days: data.window_days })
        }
      })
      .catch(() => { /* silently fall back to static data */ })
      .finally(() => { if (!cancelled) setLoadingLive(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Upcoming regulatory changes, standard revisions, and trade impacts affecting CardioWatch X1. Click any item to see device-specific implications and recommended steps.
        </p>
        {liveSource ? (
          <p style={{ fontSize: 11, color: 'var(--accent-text)', marginTop: 6 }}>
            Live · Carver Feeds · {liveSource.window_days}d window ·{' '}
            {new Date(liveSource.generated_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </p>
        ) : !loadingLive ? (
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 6 }}>
            Static data — run <code style={{ fontSize: 10 }}>python scripts/fetch_feeds.py && python scripts/vectorize_feeds.py</code> to go live
          </p>
        ) : null}
      </div>

      {/* Timeline strip */}
      <div style={{ position: 'relative', padding: '0 8px', marginBottom: 24 }}>
        <div style={{
          position: 'absolute', top: 10, left: 8, right: 8,
          height: 2, background: 'var(--border-tertiary)',
        }} />
        <div style={{ display: 'flex' }}>
          {HORIZON_QUARTERS.map((q, i) => (
            <div key={q} style={{ flex: 1, textAlign: 'center', position: 'relative' }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', margin: '4px auto 8px', position: 'relative', zIndex: 1,
                background: i < 2 ? '#d97706' : '#4d6400',
                border: '2px solid var(--bg-tertiary)',
              }} />
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{q}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="two-col">
        {items.map((item, i) => <HorizonItem key={i} item={item} />)}
      </div>
    </>
  )
}
