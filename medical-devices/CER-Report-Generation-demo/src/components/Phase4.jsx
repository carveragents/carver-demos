import { useState } from 'react'
import { CER_SECTIONS, CER_STATS, CER_PRIORITY } from '../data/cerData'

const SECTION_STATUS = {
  ok:       { dot: '#16a34a', bg: '#dcfce7',  color: '#166534', label: 'Up to date'      },
  warning:  { dot: '#d97706', bg: '#fef3c7',  color: '#92400e', label: 'Needs review'    },
  critical: { dot: '#dc2626', bg: '#fee2e2',  color: '#991b1b', label: 'Action required' },
}

const EFFORT_STYLE = {
  high:   { label: 'High effort',   bg: '#fee2e2', color: '#991b1b' },
  medium: { label: 'Medium effort', bg: '#fef3c7', color: '#92400e' },
  low:    { label: 'Low effort',    bg: '#dcfce7', color: '#166534' },
}

const PRIORITY_LEVEL = {
  critical: { dot: '#dc2626' },
  warning:  { dot: '#d97706' },
  info:     { dot: '#2563eb' },
}

const STAT_LEVEL = {
  warning:  { color: '#d97706' },
  critical: { color: '#dc2626' },
  info:     { color: '#2563eb' },
  ok:       { color: '#16a34a' },
}

const PROGRESS_STATES = ['todo', 'in-progress', 'done']
const PROGRESS_LABEL  = { todo: 'To Do', 'in-progress': 'In Progress', done: 'Done' }
const PROGRESS_STYLE  = {
  todo:         { bg: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: 'var(--border-tertiary)' },
  'in-progress':{ bg: '#fef3c7', color: '#92400e', border: '#fde68a' },
  done:         { bg: '#dcfce7', color: '#166534', border: '#bbf7d0' },
}

function daysUntil(dateStr) {
  const target = new Date(dateStr)
  const now = new Date()
  return Math.max(0, Math.ceil((target - now) / (1000 * 60 * 60 * 24)))
}

// ── CER Section row ───────────────────────────────────────────────────────────

function SectionRow({ sec, index, total }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = SECTION_STATUS[sec.status] || SECTION_STATUS.ok
  const eff = EFFORT_STYLE[sec.effort] || EFFORT_STYLE.low

  return (
    <div style={{ borderBottom: index < total - 1 ? '0.5px solid var(--border-tertiary)' : 'none' }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', gap: 12, cursor: sec.status !== 'ok' ? 'pointer' : 'default' }}
        onClick={() => sec.status !== 'ok' && setExpanded(e => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1, minWidth: 0 }}>{sec.name}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flexShrink: 0, maxWidth: 200 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            {sec.status !== 'ok' && (
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
            )}
            <span className="tag" style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.dot}33` }}>
              {cfg.label}
            </span>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'right', lineHeight: 1.4 }}>{sec.note}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ paddingBottom: 12 }}>
          <div className="feed-item-section" style={{ marginBottom: 8 }}>
            <div className="feed-item-section-label">REQUIRED ACTION</div>
            <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{sec.action}</p>
          </div>
          <span className="tag" style={{ background: eff.bg, color: eff.color }}>{eff.label}</span>
        </div>
      )}
    </div>
  )
}

// ── Priority item ─────────────────────────────────────────────────────────────

function PriorityItem({ item, index, total, progress, onCycle }) {
  const cfg = PRIORITY_LEVEL[item.level] || PRIORITY_LEVEL.info
  const ps  = PROGRESS_STYLE[progress]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '10px 0',
        borderBottom: index < total - 1 ? '0.5px solid var(--border-tertiary)' : 'none',
      }}
    >
      <div style={{
        width: 22, height: 22, borderRadius: '50%',
        background: cfg.dot + '18',
        border: `1.5px solid ${cfg.dot}44`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, marginTop: 1,
        fontSize: 11, fontWeight: 700, color: cfg.dot,
      }}>
        {item.rank}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: progress === 'done' ? 'var(--text-tertiary)' : 'var(--text-primary)', lineHeight: 1.5, textDecoration: progress === 'done' ? 'line-through' : 'none' }}>
          {item.text}
        </div>
      </div>
      <button
        style={{
          flexShrink: 0,
          padding: '3px 10px',
          borderRadius: 5,
          fontSize: 11,
          fontWeight: 500,
          fontFamily: 'inherit',
          cursor: 'pointer',
          background: ps.bg,
          color: ps.color,
          border: `0.5px solid ${ps.border}`,
          transition: 'all 0.15s',
          whiteSpace: 'nowrap',
        }}
        onClick={onCycle}
      >
        {PROGRESS_LABEL[progress]}
      </button>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function Phase4() {
  const [progress, setProgress] = useState(() =>
    Object.fromEntries(CER_PRIORITY.map(p => [p.rank, 'todo']))
  )

  const daysLeft    = daysUntil('2026-08-01')
  const urgencyColor = daysLeft < 60 ? '#dc2626' : daysLeft < 120 ? '#d97706' : '#2563eb'

  const cycleProgress = (rank) => {
    setProgress(prev => {
      const cur = prev[rank]
      const next = PROGRESS_STATES[(PROGRESS_STATES.indexOf(cur) + 1) % PROGRESS_STATES.length]
      return { ...prev, [rank]: next }
    })
  }

  const doneCount = Object.values(progress).filter(v => v === 'done').length

  return (
    <>
      {/* Countdown + header */}
      <div className="section" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
              CER Deadline — August 2026
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 40, fontWeight: 700, color: urgencyColor, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
                {daysLeft}
              </span>
              <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>days remaining</span>
            </div>
            {doneCount > 0 && (
              <div style={{ fontSize: 12, color: '#16a34a', marginTop: 6 }}>
                {doneCount} of {CER_PRIORITY.length} priority items marked done
              </div>
            )}
          </div>
          <button
            className="btn btn-primary"
            onClick={() => alert('In the full platform this launches the AI-assisted CER drafting pipeline.')}
          >
            Generate CER Report →
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stat-grid" style={{ marginBottom: 12 }}>
        {CER_STATS.map((s, i) => (
          <div key={i} className="stat-card">
            <div className="stat-label">{s.label}</div>
            <div className="stat-value" style={{ color: STAT_LEVEL[s.level]?.color || 'var(--text-primary)' }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* CER Sections — expandable */}
      <div className="section" style={{ marginBottom: 12 }}>
        <div className="section-title">CER Section Status</div>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 10 }}>
          Click any non-green section to see required action
        </p>
        {CER_SECTIONS.map((sec, i) => (
          <SectionRow key={i} sec={sec} index={i} total={CER_SECTIONS.length} />
        ))}
      </div>

      {/* Priority order — with progress toggles */}
      <div className="section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Recommended Priority Order</div>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Click status to cycle: To Do → In Progress → Done</span>
        </div>
        {CER_PRIORITY.map((item, i) => (
          <PriorityItem
            key={item.rank}
            item={item}
            index={i}
            total={CER_PRIORITY.length}
            progress={progress[item.rank]}
            onCycle={() => cycleProgress(item.rank)}
          />
        ))}
      </div>
    </>
  )
}
