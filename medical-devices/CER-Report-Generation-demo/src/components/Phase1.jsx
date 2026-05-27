import { useState, useEffect } from 'react'
import { FEED_ITEMS, SOURCE_TYPES, SEVERITY_CONFIG } from '../data/feedItems'

const JURISDICTION_FLAG = { US: '🇺🇸', EU: '🇪🇺', AU: '🇦🇺', IN: '🇮🇳', KR: '🇰🇷' }

const SOURCE_META = {
  US: { label: 'FDA MAUDE',  color: '#16a34a', bg: 'rgba(202,239,66,0.18)', flag: '🇺🇸' },
  UK: { label: 'MHRA',       color: '#7c3aed', bg: 'rgba(167,139,250,0.12)', flag: '🇬🇧' },
  CH: { label: 'Swissmedic', color: '#dc2626', bg: '#fee2e2', flag: '🇨🇭' },
}

const SEV_STYLE = {
  death:      { bg: '#1f2937', color: '#fff',    label: 'Death'       },
  serious:    { bg: '#fee2e2', color: '#dc2626', label: 'Serious'     },
  malfunction:{ bg: '#fef3c7', color: '#d97706', label: 'Malfunction' },
  'near-miss':{ bg: '#dcfce7', color: '#16a34a', label: 'Near-miss'   },
  unknown:    { bg: '#f3f4f6', color: '#9ca3af', label: 'Unknown'     },
}

const PAGE_SIZE = 25

// ── Tag tooltip definitions ───────────────────────────────────────────────────

// ── Normalise messy date strings to sortable ISO ──────────────────────────────
function normaliseDateStr(raw) {
  if (!raw) return ''
  const s = raw.trim()
  // Already ISO YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s
  // DD.MM.YYYY
  const dmy = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/)
  if (dmy) return `${dmy[3]}-${dmy[2].padStart(2,'0')}-${dmy[1].padStart(2,'0')}`
  // "May 2024", "November 2023" etc.
  const my = s.match(/^([A-Za-z]+)\s+(\d{4})/)
  if (my) {
    const months = { jan:'01',feb:'02',mar:'03',apr:'04',may:'05',jun:'06',
                     jul:'07',aug:'08',sep:'09',oct:'10',nov:'11',dec:'12' }
    const m = months[my[1].toLowerCase().slice(0,3)]
    if (m) return `${my[2]}-${m}-01`
  }
  return ''
}

const TAG_INFO = {
  CRITICAL: {
    title: 'Critical',
    body: 'Requires immediate attention. Directly impacts device safety, regulatory compliance, or a predicate device. Action needed within days to weeks.',
  },
  HIGH: {
    title: 'High Priority',
    body: 'Significant regulatory development that affects your CER or market access. Action recommended before the next CER update cycle.',
  },
  MEDIUM: {
    title: 'Medium Priority',
    body: 'Notable update to monitor. May require minor CER amendments or awareness by regulatory affairs. No urgent action.',
  },
  LOW: {
    title: 'Low Priority',
    body: 'Informational. Unlikely to require immediate action — relevant if market expansion or next major CER revision is planned.',
  },
  REGULATORY: {
    title: 'Regulatory',
    body: 'New or updated regulation, directive, or official guidance from a competent authority (e.g. EU MDR, FDA CDRH, MHRA, TGA). May change compliance requirements.',
  },
  VIGILANCE: {
    title: 'Vigilance',
    body: 'Post-market safety signal: recalls, Field Safety Corrective Actions (FSCAs), adverse event spikes, or MDR reports from surveillance databases (MAUDE, EUDAMED, MHRA).',
  },
  STANDARDS: {
    title: 'Standards',
    body: 'New or revised harmonised standard (IEC, ISO, EN). Changes may require gap analysis against your technical file and updated Declaration of Conformity.',
  },
  TRADE: {
    title: 'Trade & Market Access',
    body: 'Tariff changes, HS code reclassifications, or import/export rules affecting device commercialisation in specific markets.',
  },
  // Source badges (Live Database)
  'FDA MAUDE': {
    title: 'FDA MAUDE (US)',
    body: 'Manufacturer and User Facility Device Experience — the FDA\'s post-market adverse event database for medical devices in the United States.',
  },
  MHRA: {
    title: 'MHRA (UK)',
    body: 'Medicines and Healthcare products Regulatory Agency — the UK competent authority. Reports here are Field Safety Notices (FSNs) and Medical Device Alerts (MDAs).',
  },
  Swissmedic: {
    title: 'Swissmedic (CH)',
    body: 'Swiss Agency for Therapeutic Products — Swiss competent authority. Reports include Field Safety Corrective Actions (FSCAs) for devices on the Swiss market.',
  },
  // Severity levels (Live Database)
  Death: {
    title: 'Death',
    body: 'The adverse event was associated with or contributed to a patient or user death. Highest severity classification across all PMS databases.',
  },
  Serious: {
    title: 'Serious Injury',
    body: 'The event caused or may have caused serious injury requiring medical intervention — hospitalisation, permanent impairment, or life-threatening condition.',
  },
  Malfunction: {
    title: 'Malfunction',
    body: 'Device failed to meet its performance specifications or intended use. No injury reported, but a recurrence could cause serious harm.',
  },
  'Near-miss': {
    title: 'Near-miss',
    body: 'A malfunction or use error occurred but did not result in patient harm. Reportable because a recurrence in different circumstances could cause injury.',
  },
}

function TagTooltip({ label, tagClass, children }) {
  const [visible, setVisible] = useState(false)
  const key = label.toUpperCase()
  const info = TAG_INFO[key] || TAG_INFO[label]
  // No tooltip info — render children as-is (no wrapper)
  if (!info) return tagClass ? <span className={`tag ${tagClass}`}>{children}</span> : <>{children}</>

  return (
    <span style={{ position: 'relative', display: 'inline-block' }}
          onMouseEnter={() => setVisible(true)}
          onMouseLeave={() => setVisible(false)}
          onClick={e => e.stopPropagation()}>
      {tagClass
        ? <span className={`tag ${tagClass}`} style={{ cursor: 'help', borderBottom: '1px dashed currentColor' }}>{children}</span>
        : children
      }
      {visible && (
        <div style={{
          position: 'absolute', bottom: 'calc(100% + 6px)', left: '50%', transform: 'translateX(-50%)',
          background: '#1f2124', color: '#f3f4f6', borderRadius: 8,
          padding: '10px 12px', width: 220, zIndex: 100,
          boxShadow: '0 4px 16px rgba(0,0,0,0.22)',
          pointerEvents: 'none',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 5, color: '#ffffff', letterSpacing: '0.04em' }}>
            {info.title}
          </div>
          <div style={{ fontSize: 11, color: '#d1d5db', lineHeight: 1.55 }}>{info.body}</div>
          {/* Arrow */}
          <div style={{
            position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0,
            borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
            borderTop: '6px solid #1f2124',
          }} />
        </div>
      )}
    </span>
  )
}

// ── Curated intelligence item ─────────────────────────────────────────────────

function FeedItem({ item }) {
  const [expanded, setExpanded] = useState(false)
  const sev = SEVERITY_CONFIG[item.severity]
  const src = SOURCE_TYPES[item.sourceType]

  return (
    <div
      className={`feed-item${expanded ? ' feed-item--expanded' : ''}`}
      style={{ borderLeftColor: sev.borderColor }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="feed-item-meta">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <TagTooltip label={sev.label} tagClass={sev.tagClass}>{sev.label}</TagTooltip>
          <TagTooltip label={src.label} tagClass={src.tagClass}>{src.label}</TagTooltip>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{item.time}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>· {item.category}</span>
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', flexShrink: 0 }}>
          {item.jurisdictions.map(j => (
            <span key={j} className="jurisdiction-pill">
              {JURISDICTION_FLAG[j] || ''} {j}
            </span>
          ))}
        </div>
      </div>
      <div className="feed-item-title">{item.title}</div>
      {expanded && (
        <div className="feed-item-body">
          <div className="feed-item-section">
            <div className="feed-item-section-label">WHY THIS MATTERS TO YOUR DEVICE</div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{item.why}</p>
          </div>
          <div className="feed-item-detail-grid">
            <div className="feed-item-section">
              <div className="feed-item-section-label">RECOMMENDED ACTION</div>
              <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{item.action}</p>
            </div>
            <div className="feed-item-section">
              <div className="feed-item-section-label">DEADLINE</div>
              <div style={{
                fontSize: 13, fontWeight: 600, fontFamily: 'monospace',
                color: item.severity === 'critical' ? '#dc2626' : item.severity === 'high' ? '#d97706' : 'var(--text-primary)',
              }}>{item.deadline}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>Source: {item.source}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Live database event row ───────────────────────────────────────────────────

function EventRow({ event, index, total }) {
  const [expanded, setExpanded] = useState(false)
  const srcMeta = SOURCE_META[event.country] || SOURCE_META.US
  const sevStyle = SEV_STYLE[event.severity] || SEV_STYLE.unknown

  return (
    <div style={{ borderBottom: index < total - 1 ? '0.5px solid var(--border-tertiary)' : 'none' }}>
      <div
        style={{ display: 'flex', gap: 10, padding: '9px 0', cursor: 'pointer', alignItems: 'flex-start' }}
        onClick={() => setExpanded(e => !e)}
      >
        {/* Date */}
        <div style={{ width: 86, flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
            {event.date || '—'}
          </div>
        </div>
        {/* Source badge */}
        <div style={{ width: 80, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          <TagTooltip label={srcMeta.label} tagClass="">
            <span style={{
              display: 'inline-block', fontSize: 10, fontWeight: 700,
              padding: '2px 6px', borderRadius: 3,
              background: srcMeta.bg, color: srcMeta.color,
              cursor: 'help', borderBottom: `1px dashed ${srcMeta.color}`,
            }}>
              {srcMeta.flag} {srcMeta.label}
            </span>
          </TagTooltip>
        </div>
        {/* Device info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4 }}>
            {event.device_name || '—'}
          </div>
          {event.manufacturer && (
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{event.manufacturer}</div>
          )}
        </div>
        {/* Severity */}
        <div style={{ flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          <TagTooltip label={sevStyle.label} tagClass="">
            <span style={{
              display: 'inline-block', fontSize: 10, fontWeight: 600,
              padding: '2px 7px', borderRadius: 3,
              background: sevStyle.bg, color: sevStyle.color,
              cursor: 'help', borderBottom: `1px dashed ${sevStyle.color}`,
            }}>{sevStyle.label}</span>
          </TagTooltip>
        </div>
        {/* Expand */}
        <div style={{ flexShrink: 0, fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
          {expanded ? '▲' : '▼'}
        </div>
      </div>

      {expanded && (
        <div style={{ paddingBottom: 10 }}>
          <div className="feed-item-detail-grid" style={{ gap: 8 }}>
            <div className="feed-item-section">
              <div className="feed-item-section-label">DEVICE / TYPE</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {event.device_type || event.device_name}
              </div>
            </div>
            <div className="feed-item-section">
              <div className="feed-item-section-label">EVENT TYPE</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {event.event_type || '—'}
                {event.is_recall && <span className="tag tag-red" style={{ marginLeft: 6, fontSize: 10 }}>Recall</span>}
              </div>
            </div>
          </div>
          {event.description && (
            <div className="feed-item-section" style={{ marginTop: 8 }}>
              <div className="feed-item-section-label">EVENT DESCRIPTION</div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{event.description}</p>
            </div>
          )}
          {event.source_url && (
            <div style={{ marginTop: 8 }}>
              <a href={event.source_url} target="_blank" rel="noreferrer"
                 style={{ fontSize: 11, color: '#2563eb' }}
                 onClick={e => e.stopPropagation()}>
                View original source →
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Live database tab ─────────────────────────────────────────────────────────

function LiveDatabase() {
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [events, setEvents]   = useState([])
  const [summary, setSummary] = useState(null)

  const [sourceFilter, setSourceFilter] = useState('all')
  const [sevFilter, setSevFilter]       = useState('all')
  const [page, setPage]                 = useState(0)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [sumRes, usRes, ukRes, chRes] = await Promise.all([
          fetch('/data/summary.json'),
          fetch('/data/events_us.json'),
          fetch('/data/events_uk.json'),
          fetch('/data/events_ch.json'),
        ])
        const [sum, us, uk, ch] = await Promise.all([
          sumRes.json(), usRes.json(), ukRes.json(), chRes.json()
        ])
        if (!cancelled) {
          const all = [...us, ...uk, ...ch].sort((a, b) =>
            normaliseDateStr(b.date).localeCompare(normaliseDateStr(a.date))
          )
          setEvents(all)
          setSummary(sum)
          setLoading(false)
        }
      } catch (e) {
        if (!cancelled) { setError(e.message); setLoading(false) }
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const filtered = events.filter(e => {
    const srcOk = sourceFilter === 'all' || e.country === sourceFilter
    const sevOk = sevFilter === 'all' || e.severity === sevFilter
    return srcOk && sevOk
  })

  const pages     = Math.ceil(filtered.length / PAGE_SIZE)
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleFilter = (setter) => (val) => { setter(val); setPage(0) }

  if (loading) return (
    <div className="section" style={{ textAlign: 'center', padding: '2rem' }}>
      <div style={{ display: 'inline-block', width: 20, height: 20, borderRadius: '50%', border: '2px solid #4d6400', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite', marginBottom: 10 }} />
      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading surveillance database…</p>
    </div>
  )
  if (error) return (
    <div className="section" style={{ padding: '1.5rem', color: '#dc2626', fontSize: 13 }}>
      Error loading data: {error}
    </div>
  )

  return (
    <>
      {/* Summary stats */}
      {summary && (
        <div className="stat-grid" style={{ marginBottom: 12 }}>
          {[
            { label: 'US Events (FDA)',        value: summary.by_source.US.count.toLocaleString(),    sub: 'from 10,000 raw' },
            { label: 'UK Events (MHRA)',        value: summary.by_source.UK.count.toLocaleString(),    sub: 'field safety notices' },
            { label: 'CH Events (Swissmedic)', value: summary.by_source.CH.count.toLocaleString(),    sub: 'FSCAs' },
            { label: 'Deaths Reported',         value: summary.death_count.toLocaleString(),           sub: 'cardiovascular category', color: '#dc2626' },
          ].map(s => (
            <div key={s.label} className="stat-card">
              <div className="stat-label">{s.label}</div>
              <div className="stat-value" style={{ color: s.color || 'var(--text-primary)' }}>{s.value}</div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{s.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10, alignItems: 'center' }}>
        <span className="filter-label">SOURCE</span>
        {[['all','All Sources'], ['US','🇺🇸 FDA MAUDE'], ['UK','🇬🇧 MHRA'], ['CH','🇨🇭 Swissmedic']].map(([v,l]) => (
          <button key={v} className={`filter-btn${sourceFilter === v ? ' filter-btn--active' : ''}`}
                  onClick={() => handleFilter(setSourceFilter)(v)}>
            {l}
            <span className="filter-count">
              {v === 'all' ? events.length : events.filter(e => e.country === v).length}
            </span>
          </button>
        ))}
        <span className="filter-label" style={{ marginLeft: 8 }}>SEVERITY</span>
        {[['all','All'], ['death','Death'], ['serious','Serious'], ['malfunction','Malfunction'], ['near-miss','Near-miss']].map(([v,l]) => (
          <button key={v} className={`filter-btn${sevFilter === v ? ' filter-btn--active' : ''}`}
                  onClick={() => handleFilter(setSevFilter)(v)}>
            {l}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="section" style={{ padding: '0 14px' }}>
        {/* Header */}
        <div style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: '0.5px solid var(--border-secondary)' }}>
          {[['Date', 86], ['Source', 80], ['Device / Manufacturer', null], ['Severity', 80]].map(([label, w]) => (
            <div key={label} style={{ width: w, flex: w ? undefined : 1, fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              {label}
            </div>
          ))}
          <div style={{ width: 16 }} />
        </div>

        {pageItems.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '1.5rem', fontSize: 13, color: 'var(--text-secondary)' }}>
            No events match the selected filters.
          </div>
        ) : (
          pageItems.map((e, i) => <EventRow key={e.id} event={e} index={i} total={pageItems.length} />)
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
          <button className="btn" style={{ fontSize: 12, padding: '5px 12px' }}
                  disabled={page === 0} onClick={() => setPage(p => p - 1)}>
            ← Prev
          </button>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
            {page + 1} / {pages} · {filtered.length.toLocaleString()} events
          </span>
          <button className="btn" style={{ fontSize: 12, padding: '5px 12px' }}
                  disabled={page >= pages - 1} onClick={() => setPage(p => p + 1)}>
            Next →
          </button>
        </div>
      )}
    </>
  )
}

// ── Intelligence feed tab ─────────────────────────────────────────────────────

function IntelligenceFeed() {
  const [filterSev, setFilterSev]       = useState('all')
  const [filterSource, setFilterSource] = useState('all')
  const [items, setItems]               = useState(FEED_ITEMS)
  const [liveSource, setLiveSource]     = useState(null) // { generated_at, window_days }
  const [loadingLive, setLoadingLive]   = useState(true)

  useEffect(() => {
    let cancelled = false
    fetch('/data/regulatory_feed.json')
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json() })
      .then(data => {
        if (!cancelled && data.items?.length) {
          const sorted = [...data.items].sort((a, b) => {
            const da = a.published_date ? new Date(a.published_date).getTime() : 0
            const db = b.published_date ? new Date(b.published_date).getTime() : 0
            return db - da
          })
          setItems(sorted)
          setLiveSource({ generated_at: data.generated_at, window_days: data.window_days })
        }
      })
      .catch(() => { /* silently fall back to static data */ })
      .finally(() => { if (!cancelled) setLoadingLive(false) })
    return () => { cancelled = true }
  }, [])

  const criticalCount = items.filter(i => i.severity === 'critical').length

  const filtered = items.filter(i => {
    const sevMatch = filterSev === 'all' || i.severity === filterSev
    const srcMatch = filterSource === 'all' || i.sourceType === filterSource
    return sevMatch && srcMatch
  })

  const severities = ['all', 'critical', 'high', 'medium', 'low']

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            AI-curated signals with device-specific context, recommended actions, and deadlines.
          </p>
          {liveSource ? (
            <p style={{ fontSize: 11, color: 'var(--accent-text)', marginTop: 3 }}>
              Live · Carver Feeds · {liveSource.window_days}d window ·{' '}
              {new Date(liveSource.generated_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </p>
          ) : !loadingLive ? (
            <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>
              Static data — run <code style={{ fontSize: 10 }}>python scripts/fetch_feeds.py && python scripts/vectorize_feeds.py</code> to go live
            </p>
          ) : null}
        </div>
        {criticalCount > 0 && (
          <div className="critical-alert-badge">
            <span className="critical-pulse" />
            {criticalCount} CRITICAL
          </div>
        )}
      </div>

      <div className="filter-row" style={{ marginBottom: 8 }}>
        <span className="filter-label">SEVERITY</span>
        {severities.map(s => (
          <button key={s}
            className={`filter-btn${filterSev === s ? ' filter-btn--active' : ''}`}
            style={filterSev === s && s !== 'all' ? {
              background: SEVERITY_CONFIG[s]?.borderColor + '18',
              borderColor: SEVERITY_CONFIG[s]?.borderColor + '44',
              color: SEVERITY_CONFIG[s]?.borderColor,
            } : {}}
            onClick={() => setFilterSev(s)}>
            {s.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="filter-row section" style={{ marginBottom: 12, padding: '10px 14px' }}>
        <span className="filter-label">SOURCE</span>
        <button className={`filter-btn${filterSource === 'all' ? ' filter-btn--active' : ''}`}
                onClick={() => setFilterSource('all')}>
          All Sources <span className="filter-count">{items.length}</span>
        </button>
        {Object.entries(SOURCE_TYPES).map(([key, cfg]) => {
          const count = items.filter(i => i.sourceType === key).length
          return (
            <button key={key}
              className={`filter-btn${filterSource === key ? ' filter-btn--active' : ''}`}
              onClick={() => setFilterSource(key)}>
              {cfg.label} <span className="filter-count">{count}</span>
            </button>
          )
        })}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.length === 0 ? (
          <div className="section" style={{ textAlign: 'center', padding: '2rem' }}>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 10 }}>No updates match the selected filters.</p>
            <button className="btn" onClick={() => { setFilterSev('all'); setFilterSource('all') }}>Reset filters</button>
          </div>
        ) : (
          filtered.map(item => <FeedItem key={item.id} item={item} />)
        )}
      </div>
      {filtered.length > 0 && (
        <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', fontFamily: 'monospace' }}>
          Click any item to expand · Showing {filtered.length} of {items.length} updates
          {liveSource ? ' · Powered by Carver Feeds' : ''}
        </div>
      )}
    </>
  )
}

// ── Root export ───────────────────────────────────────────────────────────────

export default function Phase1() {
  const [tab, setTab] = useState('intelligence')

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
          {tab === 'intelligence' ? "This Week's Intelligence" : 'Live Surveillance Database'}
        </h3>
        <div className="tab-row" style={{ marginBottom: 0, borderBottom: 'none' }}>
          <div className={`tab${tab === 'intelligence' ? ' active' : ''}`}
               onClick={() => setTab('intelligence')}>
            Intelligence Feed
          </div>
          <div className={`tab${tab === 'live' ? ' active' : ''}`}
               onClick={() => setTab('live')}>
            Live Database
            <span className="tab-badge">2,056</span>
          </div>
        </div>
      </div>

      {tab === 'intelligence' && <IntelligenceFeed />}
      {tab === 'live'         && <LiveDatabase />}
    </>
  )
}
