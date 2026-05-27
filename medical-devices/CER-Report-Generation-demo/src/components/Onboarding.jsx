import { useState, useEffect, useRef } from 'react'
import { K510_DOC, PARSE_STEPS } from '../data/k510Data'

// ── Upload screen ─────────────────────────────────────────────────────────────

function UploadScreen({ onLoad }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    onLoad() // in the real product, read e.dataTransfer.files[0]
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      {/* Hero headline */}
      <div style={{ marginBottom: 28, textAlign: 'center' }}>
        <div style={{
          display: 'inline-block',
          background: 'rgba(202,239,66,0.18)',
          color: '#4d6400',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.07em',
          padding: '3px 10px',
          borderRadius: 4,
          marginBottom: 12,
        }}>
          STEP 1 OF 1
        </div>
        <h3 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.35, marginBottom: 8 }}>
          Upload your 510(k) submission
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          The platform reads your submission and builds a device-specific surveillance context — tuning every signal, predicate comparison, and CER section to your exact device profile.
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`upload-dropzone${dragging ? ' upload-dropzone--active' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
      >
        <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }}
               onChange={onLoad} />
        <div className="upload-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
          {dragging ? 'Drop to analyse' : 'Drag & drop your 510(k) PDF'}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          PDF, DOCX, or plain text · 510(k), De Novo, or PMA
        </div>
      </div>

      {/* Divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '18px 0' }}>
        <div style={{ flex: 1, height: '0.5px', background: 'var(--border-tertiary)' }} />
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>or</span>
        <div style={{ flex: 1, height: '0.5px', background: 'var(--border-tertiary)' }} />
      </div>

      {/* Demo button */}
      <button className="btn btn-primary" style={{ width: '100%', padding: '12px', fontSize: 14 }} onClick={onLoad}>
        Load Demo 510(k) — CardioWatch X1
      </button>
      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', lineHeight: 1.6 }}>
        Uses a pre-built 510(k) for a Class II cardiovascular wearable monitor.<br/>
        All downstream signals, predicates, and CER sections are tuned to this device.
      </div>
    </div>
  )
}

// ── Parsing animation ─────────────────────────────────────────────────────────

function ParsingScreen({ onDone }) {
  const [completed, setCompleted] = useState([])
  const [currentIdx, setCurrentIdx] = useState(0)

  useEffect(() => {
    if (currentIdx >= PARSE_STEPS.length) {
      setTimeout(onDone, 600)
      return
    }
    const step = PARSE_STEPS[currentIdx]
    const t = setTimeout(() => {
      setCompleted(prev => [...prev, currentIdx])
      setCurrentIdx(i => i + 1)
    }, step.duration)
    return () => clearTimeout(t)
  }, [currentIdx, onDone])

  const pct = Math.round((completed.length / PARSE_STEPS.length) * 100)

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <div style={{ marginBottom: 24, textAlign: 'center' }}>
        <div style={{
          display: 'inline-block',
          background: 'rgba(202,239,66,0.18)', color: '#4d6400',
          fontSize: 11, fontWeight: 700, letterSpacing: '0.07em',
          padding: '3px 10px', borderRadius: 4, marginBottom: 12,
        }}>
          ANALYSING DOCUMENT
        </div>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
          K213456_CardioWatch_X1_510k.pdf
        </h3>
        {/* Progress bar */}
        <div style={{ height: 4, background: 'var(--border-tertiary)', borderRadius: 4, overflow: 'hidden', margin: '0 auto 6px', maxWidth: 360 }}>
          <div style={{
            height: '100%',
            width: `${pct}%`,
            background: '#caef42',
            borderRadius: 4,
            transition: 'width 0.3s ease',
          }} />
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{pct}%</div>
      </div>

      <div className="section" style={{ padding: '14px 16px' }}>
        {PARSE_STEPS.map((step, i) => {
          const done   = completed.includes(i)
          const active = currentIdx === i
          return (
            <div key={i} className="parse-step" style={{
              opacity: done || active ? 1 : 0.35,
              borderBottom: i < PARSE_STEPS.length - 1 ? '0.5px solid var(--border-tertiary)' : 'none',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {/* Status icon */}
                <div style={{ width: 18, height: 18, flexShrink: 0 }}>
                  {done ? (
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <circle cx="9" cy="9" r="9" fill="#dcfce7"/>
                      <polyline points="5,9 8,12 13,6" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                    </svg>
                  ) : active ? (
                    <div style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid #4d6400', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite' }} />
                  ) : (
                    <div style={{ width: 18, height: 18, borderRadius: '50%', border: '1.5px solid var(--border-tertiary)' }} />
                  )}
                </div>
                {/* Label */}
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 12, color: active ? 'var(--text-primary)' : done ? 'var(--text-secondary)' : 'var(--text-tertiary)' }}>
                    {step.label}
                  </span>
                </div>
                {/* Result */}
                {done && (
                  <span style={{ fontSize: 11, color: '#16a34a', fontFamily: 'monospace', flexShrink: 0, maxWidth: 220, textAlign: 'right' }}>
                    {step.result}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Parsed summary ────────────────────────────────────────────────────────────

const SECTION_KEYS = [
  { key: 'device_description',    label: 'Device Description',        tagClass: 'tag-blue'   },
  { key: 'indications_for_use',   label: 'Indications for Use',        tagClass: 'tag-teal'   },
  { key: 'predicate_devices',     label: 'Predicate Devices',          tagClass: 'tag-amber'  },
  { key: 'substantial_equivalence', label: 'Substantial Equivalence',  tagClass: 'tag-green'  },
  { key: 'performance_summary',   label: 'Performance Data',           tagClass: 'tag-purple' },
  { key: 'regulatory_history',    label: 'Regulatory History',         tagClass: 'tag-gray'   },
]

function DocSection({ title, tagClass, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: '0.5px solid var(--border-tertiary)' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', cursor: 'pointer', gap: 8 }}
        onClick={() => setOpen(o => !o)}
      >
        <span className={`tag ${tagClass}`}>{title}</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && <div style={{ paddingBottom: 14 }}>{children}</div>}
    </div>
  )
}

function ParsedSummary({ onContinue }) {
  const d = K510_DOC

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span style={{ fontSize: 12, color: '#16a34a', fontWeight: 500 }}>Document analysed successfully</span>
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>{d.meta.device_name}</h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            {d.meta.applicant} · {d.meta.submission_type} · {d.meta.k_number}
          </p>
        </div>
        <button className="btn btn-primary" style={{ padding: '10px 20px', fontSize: 14 }} onClick={onContinue}>
          Begin Surveillance →
        </button>
      </div>

      {/* Key facts strip */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 8, marginBottom: 16,
      }}>
        {[
          { label: 'Classification',  value: `Class ${d.meta.device_class}` },
          { label: 'Regulation',      value: d.meta.regulation_number },
          { label: 'Predicates',      value: `${d.predicate_devices.length} devices` },
          { label: 'Decision',        value: d.meta.decision },
        ].map(f => (
          <div key={f.label} className="stat-card">
            <div className="stat-label">{f.label}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 3 }}>{f.value}</div>
          </div>
        ))}
      </div>

      {/* Expandable sections */}
      <div className="section">
        <div className="section-title" style={{ marginBottom: 4 }}>Extracted Document Sections</div>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 10 }}>Click any section to review extracted data</p>

        <DocSection title="Device Description" tagClass="tag-blue">
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 10 }}>
            {d.device_description.summary}
          </p>
          <div className="feed-item-section-label">KEY TECHNOLOGIES</div>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {d.device_description.technology.map((t, i) => (
              <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{t}</li>
            ))}
          </ul>
        </DocSection>

        <DocSection title="Indications for Use" tagClass="tag-teal">
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 10 }}>
            {d.indications_for_use.cleared_indication}
          </p>
          <div className="feed-item-section-label">CONTRAINDICATIONS</div>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {d.indications_for_use.contraindications.map((c, i) => (
              <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{c}</li>
            ))}
          </ul>
        </DocSection>

        <DocSection title="Predicate Devices" tagClass="tag-amber">
          {d.predicate_devices.map((p, i) => (
            <div key={i} style={{ marginBottom: i < d.predicate_devices.length - 1 ? 14 : 0, paddingBottom: i < d.predicate_devices.length - 1 ? 14 : 0, borderBottom: i < d.predicate_devices.length - 1 ? '0.5px solid var(--border-tertiary)' : 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{p.k_number}</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 4 }}>{p.intended_use_similarity}</p>
              <span className="tag tag-green" style={{ fontSize: 10 }}>{p.equivalence_conclusion}</span>
            </div>
          ))}
        </DocSection>

        <DocSection title="Substantial Equivalence" tagClass="tag-green">
          <div style={{ marginBottom: 10 }}>
            <span className="tag tag-green">{d.substantial_equivalence.conclusion}</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 10 }}>
            {d.substantial_equivalence.basis}
          </p>
          <div className="feed-item-section-label">RISK SUMMARY</div>
          {d.substantial_equivalence.risk_summary.map((r, i) => (
            <div key={i} style={{ marginTop: 8, padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{r.risk}</span>
                <span className={`tag ${r.severity === 'High' ? 'tag-red' : r.severity === 'Medium' ? 'tag-amber' : 'tag-green'}`} style={{ fontSize: 10 }}>
                  {r.severity}
                </span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{r.mitigation}</p>
            </div>
          ))}
        </DocSection>

        <DocSection title="Performance Data" tagClass="tag-purple">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 10 }}>
            {[
              { label: 'AF Sensitivity', value: d.performance_summary.af_detection.sensitivity },
              { label: 'AF Specificity', value: d.performance_summary.af_detection.specificity },
              { label: 'PPV',            value: d.performance_summary.af_detection.ppv },
              { label: 'NPV',            value: d.performance_summary.af_detection.npv },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <div className="stat-label">{s.label}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginTop: 3 }}>{s.value}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Dataset: {d.performance_summary.af_detection.dataset}</p>
        </DocSection>

        <DocSection title="Regulatory History" tagClass="tag-gray">
          {[
            { market: 'US FDA',    status: `510(k) ${d.meta.k_number} · Cleared ${d.meta.decision_date}` },
            { market: 'EU MDR',   status: d.regulatory_history.eu_status },
            { market: 'Australia',status: d.regulatory_history.au_status },
            { market: 'India',    status: d.regulatory_history.in_status },
          ].map(m => (
            <div key={m.market} style={{ display: 'flex', padding: '7px 0', borderBottom: '0.5px solid var(--border-tertiary)', gap: 12 }}>
              <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', flexShrink: 0, width: 80 }}>{m.market}</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{m.status}</span>
            </div>
          ))}
        </DocSection>
      </div>
    </div>
  )
}

// ── Root export ───────────────────────────────────────────────────────────────

export default function Onboarding({ onComplete }) {
  const [stage, setStage] = useState('upload') // 'upload' | 'parsing' | 'summary'

  return (
    <div className="onboarding-wrap">
      {stage === 'upload'  && <UploadScreen onLoad={() => setStage('parsing')} />}
      {stage === 'parsing' && <ParsingScreen onDone={() => setStage('summary')} />}
      {stage === 'summary' && <ParsedSummary onContinue={onComplete} />}
    </div>
  )
}
