import { useState, useEffect } from 'react'
import { PREDICATE_DEVICES } from '../data/predicates'

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({ data, color, width = 240, height = 32 }) {
  const max   = Math.max(...data, 1)
  const min   = Math.min(...data)
  const range = max - min || 1
  const pts   = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')
  const lastX = width
  const lastY = height - ((data[data.length - 1] - min) / range) * (height - 4) - 2
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="3" fill={color} />
    </svg>
  )
}

// ── Predicate card ────────────────────────────────────────────────────────────

const STATUS_STYLE = {
  critical: { bg: '#fee2e2', color: '#dc2626' },
  high:     { bg: '#fef3c7', color: '#d97706' },
  success:  { bg: '#dcfce7', color: '#16a34a' },
}

function PredicateCard({ device }) {
  const [expanded, setExpanded] = useState(false)
  const [flagged, setFlagged]   = useState(false)
  const s = STATUS_STYLE[device.statusLevel] || STATUS_STYLE.success

  return (
    <div className="section predicate-card" onClick={() => setExpanded(e => !e)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{device.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2, fontFamily: 'monospace' }}>
            {device.k_number} · {device.role}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
          <span className="tag" style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}33` }}>
            {device.status}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 14 }}>
        <div>
          <div className="stat-label">AEs (90d)</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>{device.events_90d}</div>
          <div style={{ fontSize: 11, marginTop: 2, fontFamily: 'monospace', color: device.trend === 'up' ? '#dc2626' : '#16a34a' }}>
            {device.trend === 'up' ? '▲' : '▼'} {device.trendPct}% vs prev
          </div>
        </div>
        <div>
          <div className="stat-label">FSCAs</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 2, color: device.fscas > 0 ? '#d97706' : 'var(--text-primary)' }}>{device.fscas}</div>
        </div>
        <div>
          <div className="stat-label">Recalls</div>
          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 2, color: device.recalls > 0 ? '#dc2626' : 'var(--text-primary)' }}>{device.recalls}</div>
        </div>
      </div>

      <div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace', letterSpacing: '0.06em', marginBottom: 6 }}>
          AE TREND (12 MONTHS)
        </div>
        <Sparkline data={device.sparkline} color={s.color} width={260} height={32} />
      </div>

      {expanded && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: '0.5px solid var(--border-tertiary)' }}
             onClick={e => e.stopPropagation()}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace', letterSpacing: '0.06em', marginBottom: 8 }}>
              MONTHLY AE BREAKDOWN
            </div>
            <div style={{ display: 'flex', gap: 0, overflowX: 'auto' }}>
              {device.months.map((m, i) => {
                const val  = device.sparkline[i]
                const peak = Math.max(...device.sparkline)
                const isLast = i === device.months.length - 1
                return (
                  <div key={m} style={{ flex: 1, minWidth: 34, textAlign: 'center' }}>
                    <div style={{ fontSize: 11, fontWeight: isLast ? 700 : 400, color: isLast ? s.color : 'var(--text-primary)', fontFamily: 'monospace' }}>{val}</div>
                    <div style={{ height: 32, margin: '3px 2px', background: s.color + Math.round((val / peak) * 150 + 30).toString(16).padStart(2,'0'), borderRadius: 3 }} />
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{m}</div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="feed-item-section" style={{ marginBottom: 10 }}>
            <div className="feed-item-section-label">IDENTIFIED FAILURE MODES</div>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {device.failureModes.map((fm, i) => (
                <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{fm}</li>
              ))}
            </ul>
          </div>

          <div className="feed-item-section" style={{ marginBottom: 10 }}>
            <div className="feed-item-section-label">IMPLICATION FOR CARDIOWATCH X1</div>
            <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{device.implications}</p>
          </div>

          <div className="feed-item-section" style={{ marginBottom: 14 }}>
            <div className="feed-item-section-label">REGULATORY ACTIONS</div>
            {device.regulatoryActions.map((ra, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: i < device.regulatoryActions.length - 1 ? '0.5px solid var(--border-tertiary)' : 'none' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ra.label}</span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace', flexShrink: 0, marginLeft: 12 }}>{ra.date}</span>
              </div>
            ))}
          </div>

          <button
            className={`btn${flagged ? ' btn-primary' : ''}`}
            style={{ fontSize: 12, padding: '6px 12px' }}
            onClick={() => setFlagged(f => !f)}
          >
            {flagged ? '✓ Flagged for CER Review' : 'Flag for CER Review'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Device landscape (real data) ──────────────────────────────────────────────

const SEV_COLOR = {
  death:       '#111827',
  serious:     '#dc2626',
  malfunction: '#d97706',
  'near-miss': '#16a34a',
  unknown:     '#6b7280',
}

const SEV_ORDER = ['death', 'serious', 'malfunction', 'near-miss', 'unknown']

function normalizeType(dt) {
  const s = (dt || '').toUpperCase()
  if (/SUBCUTANEOUS|S.ICD/.test(s))                                      return 'Subcutaneous ICD (S-ICD)'
  if (/CRT/.test(s) && /DEFIBRILLAT|CARDIOVERTER/.test(s))               return 'CRT-D (Cardiac Resync)'
  if (/DEFIBRILLAT|CARDIOVERTER|\bICD\b/.test(s))                        return 'ICD (Non-CRT)'
  if (/ELECTRODE|LEAD|TRANSVENE/.test(s))                                return 'ICD Lead / Electrode'
  if (/PHYSIOLOG.*MONITOR|MONITOR.*PHYSIOLOG|SINGLE.PATIENT.*MONITOR|TRANSPORTABLE.*MONITOR/.test(s))
                                                                          return 'Cardiac Monitoring System'
  if (/DEFIBRIL.*MONITOR|MONITOR.*DEFIBRIL|DEFIBRILLAT.*SYSTEM/.test(s)) return 'Defibrillator / Monitor'
  if (/VENTRICULAR.*ASSIST|CIRCULATORY.*ASSIST|BALLOON.*PUMP|INTRA.AORTIC/.test(s))
                                                                          return 'Cardiac Support Device'
  if (/VALVE|PROSTHESIS|BYPASS|HEART.LUNG|CATHETER|ANGIOGRAPH|STENT|VASCULAR/.test(s))
                                                                          return 'Vascular / Structural'
  return 'Other Cardiovascular'
}

const RELEVANCE = {
  'Cardiac Monitoring System':   { label: 'Direct comparator',   color: '#dc2626' },
  'Defibrillator / Monitor':     { label: 'Direct comparator',   color: '#dc2626' },
  'ICD (Non-CRT)':               { label: 'Same therapeutic area', color: '#d97706' },
  'CRT-D (Cardiac Resync)':      { label: 'Same therapeutic area', color: '#d97706' },
  'Subcutaneous ICD (S-ICD)':    { label: 'Same therapeutic area', color: '#d97706' },
  'ICD Lead / Electrode':        { label: 'Companion device',    color: '#2563eb' },
  'Cardiac Support Device':      { label: 'Same therapeutic area', color: '#d97706' },
  'Vascular / Structural':       { label: 'Adjacent specialty',  color: '#6b7280' },
  'Other Cardiovascular':        { label: 'Adjacent specialty',  color: '#6b7280' },
}

function SeverityBar({ counts, total }) {
  return (
    <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', width: '100%' }}>
      {SEV_ORDER.map(sev => {
        const pct = ((counts[sev] || 0) / total) * 100
        if (!pct) return null
        return (
          <div key={sev} title={`${sev}: ${counts[sev]}`}
               style={{ width: `${pct}%`, background: SEV_COLOR[sev], minWidth: pct > 0 ? 2 : 0 }} />
        )
      })}
    </div>
  )
}

function DeviceGroupCard({ group }) {
  const [expanded, setExpanded] = useState(false)
  const [evPage, setEvPage]     = useState(0)
  const EV_PAGE = 10

  const rel     = RELEVANCE[group.name] || RELEVANCE['Other Cardiovascular']
  const topMfrs = Object.entries(group.manufacturers)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 3)
  const srcColors = { US: '#16a34a', UK: '#7c3aed', CH: '#dc2626' }

  return (
    <div className="section" style={{ cursor: 'pointer' }} onClick={() => { setExpanded(e => !e); setEvPage(0) }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{group.name}</span>
            <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: rel.color + '18', color: rel.color, border: `1px solid ${rel.color}33` }}>
              {rel.label}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.entries(group.by_country).map(([c, n]) => (
              <span key={c} style={{ fontSize: 11, padding: '1px 6px', borderRadius: 3, background: srcColors[c] + '18', color: srcColors[c], fontFamily: 'monospace' }}>
                {c}: {n}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>{group.total.toLocaleString()}</div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>AEs reported</div>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Severity bar */}
      <div style={{ marginBottom: 8 }}>
        <SeverityBar counts={group.severity} total={group.total} />
        <div style={{ display: 'flex', gap: 10, marginTop: 5, flexWrap: 'wrap' }}>
          {SEV_ORDER.filter(s => group.severity[s]).map(s => (
            <span key={s} style={{ fontSize: 10, color: SEV_COLOR[s], fontFamily: 'monospace' }}>
              {group.severity[s]} {s}
            </span>
          ))}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '0.5px solid var(--border-tertiary)' }}
             onClick={e => e.stopPropagation()}>

          {/* Top manufacturers */}
          <div className="feed-item-section" style={{ marginBottom: 12 }}>
            <div className="feed-item-section-label">TOP MANUFACTURERS</div>
            {topMfrs.map(([mfr, cnt], i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < topMfrs.length - 1 ? '0.5px solid var(--border-tertiary)' : 'none' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  {mfr || 'Unknown'}
                </span>
                <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--text-tertiary)', flexShrink: 0, marginLeft: 12 }}>
                  {cnt} events
                </span>
              </div>
            ))}
          </div>

          {/* Recent events */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
              <div className="feed-item-section-label">RECENT EVENTS</div>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                {group.events.length} total · showing {Math.min((evPage + 1) * EV_PAGE, group.events.length)} of {group.events.length}
              </span>
            </div>

            {group.events.slice(0, (evPage + 1) * EV_PAGE).map((ev, i) => {
              const sevCol = SEV_COLOR[ev.severity] || SEV_COLOR.unknown
              return (
                <div key={ev.id} style={{ display: 'flex', gap: 10, padding: '7px 0', borderBottom: '0.5px solid var(--border-tertiary)', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace', flexShrink: 0, width: 82 }}>{ev.date || '—'}</span>
                  <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: (srcColors[ev.country] || '#16a34a') + '18', color: srcColors[ev.country] || '#16a34a', flexShrink: 0 }}>
                    {ev.country}
                  </span>
                  <span style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {ev.device_name}
                    {ev.manufacturer && <span style={{ color: 'var(--text-tertiary)' }}> · {ev.manufacturer}</span>}
                  </span>
                  <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, background: sevCol + '18', color: sevCol, flexShrink: 0, fontWeight: 600 }}>
                    {ev.severity}
                  </span>
                </div>
              )
            })}

            {group.events.length > (evPage + 1) * EV_PAGE && (
              <button className="btn" style={{ width: '100%', fontSize: 12, padding: '6px', marginTop: 8 }}
                      onClick={() => setEvPage(p => p + 1)}>
                Load more events
              </button>
            )}

            {group.events[0]?.source_url && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-tertiary)' }}>
                Sources include:{' '}
                <a href={group.events[0].source_url} target="_blank" rel="noreferrer"
                   style={{ color: '#2563eb' }}>
                  {group.events[0].source} →
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function DeviceLandscape() {
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [groups, setGroups]   = useState([])
  const [summary, setSummary] = useState(null)
  const [sourceFilter, setSourceFilter] = useState('all')

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
        if (cancelled) return

        const all = [...us, ...uk, ...ch]
        const byType = {}
        for (const ev of all) {
          const key = normalizeType(ev.device_type)
          if (!byType[key]) byType[key] = { name: key, total: 0, severity: {}, manufacturers: {}, by_country: {}, events: [] }
          const g = byType[key]
          g.total++
          const sev = ev.severity || 'unknown'
          g.severity[sev] = (g.severity[sev] || 0) + 1
          if (ev.manufacturer) g.manufacturers[ev.manufacturer] = (g.manufacturers[ev.manufacturer] || 0) + 1
          g.by_country[ev.country] = (g.by_country[ev.country] || 0) + 1
          g.events.push(ev)
        }
        // Sort events within each group by date desc
        for (const g of Object.values(byType)) {
          g.events.sort((a, b) => (b.date || '').localeCompare(a.date || ''))
        }
        const sorted = Object.values(byType).sort((a, b) => b.total - a.total)
        setGroups(sorted)
        setSummary(sum)
        setLoading(false)
      } catch (e) {
        if (!cancelled) { setError(e.message); setLoading(false) }
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const filtered = sourceFilter === 'all'
    ? groups
    : groups.map(g => ({
        ...g,
        events:     g.events.filter(e => e.country === sourceFilter),
        total:      g.events.filter(e => e.country === sourceFilter).length,
        by_country: { [sourceFilter]: g.events.filter(e => e.country === sourceFilter).length },
        severity:   g.events.filter(e => e.country === sourceFilter).reduce((acc, e) => {
                      const s = e.severity || 'unknown'
                      acc[s] = (acc[s] || 0) + 1
                      return acc
                    }, {}),
      })).filter(g => g.total > 0).sort((a, b) => b.total - a.total)

  if (loading) return (
    <div className="section" style={{ textAlign: 'center', padding: '2rem' }}>
      <div style={{ display: 'inline-block', width: 20, height: 20, borderRadius: '50%', border: '2px solid #4d6400', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite', marginBottom: 10 }} />
      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading device landscape data…</p>
    </div>
  )
  if (error) return (
    <div className="section" style={{ padding: '1.5rem', fontSize: 13, color: '#dc2626' }}>Error: {error}</div>
  )

  const totalEvents = summary?.total || 0

  return (
    <>
      {/* Summary strip */}
      <div className="stat-grid" style={{ marginBottom: 12 }}>
        {[
          { label: 'Total Cardio Events',  value: totalEvents.toLocaleString(), sub: 'across 3 databases' },
          { label: 'Device Categories',    value: groups.length,                sub: 'normalised from raw types' },
          { label: 'Death Events',         value: summary?.death_count || 0,    sub: 'reported in dataset', color: '#dc2626' },
          { label: 'Date Range',           value: 'Jan–Mar 2026',               sub: 'latest snapshot' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ color: s.color || 'var(--text-primary)' }}>{s.value}</div>
            {s.sub && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Source filter */}
      <div className="filter-row" style={{ marginBottom: 12 }}>
        <span className="filter-label">SOURCE</span>
        {[['all','All (US + UK + CH)'], ['US','🇺🇸 FDA MAUDE'], ['UK','🇬🇧 MHRA'], ['CH','🇨🇭 Swissmedic']].map(([v, l]) => (
          <button key={v} className={`filter-btn${sourceFilter === v ? ' filter-btn--active' : ''}`}
                  onClick={() => setSourceFilter(v)}>
            {l}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Severity bar:</span>
        {SEV_ORDER.map(s => (
          <span key={s} style={{ fontSize: 11, color: SEV_COLOR[s], display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: SEV_COLOR[s], borderRadius: 2 }} />
            {s}
          </span>
        ))}
      </div>

      {/* Device group cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {filtered.map(g => <DeviceGroupCard key={g.name} group={g} />)}
      </div>

      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', fontFamily: 'monospace' }}>
        Click any category to expand · Sources: FDA MAUDE · MHRA · Swissmedic
      </div>
    </>
  )
}

// ── Root export ───────────────────────────────────────────────────────────────

export default function Phase2() {
  const [tab, setTab] = useState('predicates')
  const atRisk = PREDICATE_DEVICES.filter(d => d.statusLevel !== 'success').length

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
          {tab === 'predicates' ? 'Declared Predicates — K213456' : 'Cardiovascular Device Landscape'}
        </h3>
        <div className="tab-row" style={{ marginBottom: 0, borderBottom: 'none' }}>
          <div className={`tab${tab === 'predicates' ? ' active' : ''}`} onClick={() => setTab('predicates')}>
            Predicates
            {atRisk >= 2 && <span className="tab-badge">{atRisk}</span>}
          </div>
          <div className={`tab${tab === 'landscape' ? ' active' : ''}`} onClick={() => setTab('landscape')}>
            Live Device Landscape
          </div>
        </div>
      </div>

      {tab === 'predicates' && (
        <>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
            Monitoring predicate and substantially equivalent devices declared in 510(k) K213456. Click any card to view failure mode analysis.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {PREDICATE_DEVICES.map(d => <PredicateCard key={d.k_number} device={d} />)}
          </div>
          {atRisk >= 2 && (
            <div className="attention-banner">
              <div className="attention-banner-title">⚠ ATTENTION REQUIRED</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {atRisk} of {PREDICATE_DEVICES.length} predicate devices show deteriorating safety profiles.
                Your equivalence argument and clinical evaluation may require reassessment before the Aug 2026 CER deadline.
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'landscape' && <DeviceLandscape />}
    </>
  )
}
