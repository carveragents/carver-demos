import { useState, useEffect } from 'react'

// ── Article card ──────────────────────────────────────────────────────────────

function ArticleCard({ article }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="section"
      style={{ padding: '12px 14px', cursor: 'pointer', marginBottom: 8 }}
      onClick={() => setExpanded(e => !e)}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 7 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span className={`tag ${article.tag_class}`} style={{ fontSize: 9, letterSpacing: '0.05em' }}>
            {article.type_label}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            {article.journal?.length > 45 ? article.journal.slice(0, 45) + '…' : article.journal}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
            {article.pub_date_display}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Title */}
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4, marginBottom: 4 }}>
        {article.title}
      </div>

      {/* Authors + relevance */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{article.authors}</div>
        <div style={{
          fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 4,
          background: article.score > 0.12 ? '#dcfce7' : article.score > 0.07 ? '#fef3c7' : '#f3f4f6',
          color:      article.score > 0.12 ? '#166534' : article.score > 0.07 ? '#92400e' : '#6b7280',
        }}>
          {article.score > 0.12 ? 'High relevance' : article.score > 0.07 ? 'Relevant' : 'Peripheral'}
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-dim)' }}
             onClick={e => e.stopPropagation()}>
          {article.abstract && (
            <div className="feed-item-section" style={{ marginBottom: 10 }}>
              <div className="feed-item-section-label">ABSTRACT</div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65 }}>
                {article.abstract.length > 600 ? article.abstract.slice(0, 600) + '…' : article.abstract}
              </p>
            </div>
          )}
          {article.mesh_terms?.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div className="feed-item-section-label" style={{ marginBottom: 6 }}>MESH TERMS</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {article.mesh_terms.slice(0, 10).map((t, i) => (
                  <span key={i} className="tag tag-gray" style={{ fontSize: 10 }}>{t.split('/')[0]}</span>
                ))}
              </div>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {article.pubmed_url && (
              <a href={article.pubmed_url} target="_blank" rel="noreferrer"
                 style={{ fontSize: 12, color: '#2563eb' }}>
                View on PubMed →
              </a>
            )}
            {article.doi && (
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
                DOI: {article.doi}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Clearance card ────────────────────────────────────────────────────────────

const REASON_SHORT = {
  'Change Design/Components/Specifications/Material': 'Design / Component Change',
  'Labeling Change - Indications/instructions/shelf life/tradename': 'Labeling — Indications',
  'Labeling Change - PAS': 'Labeling — PAS',
  'Process Change - Manufacturer/Sterilizer/Packager/Supplier': 'Process Change',
  'Location Change - Manufacturer/Sterilizer/Packager/Supplier': 'Location Change',
  'Postapproval Study Protocol': 'Post-Approval Study',
  'Postapproval Study Protocol - OSB': 'Post-Approval Study',
  'Express GMP Supplement': 'GMP Supplement',
  'Other': 'Other',
}

const REASON_COLOR = {
  'Change Design/Components/Specifications/Material': { bg: '#dbeafe', color: '#1e40af' },
  'Labeling Change - Indications/instructions/shelf life/tradename': { bg: '#dcfce7', color: '#166534' },
  'Labeling Change - PAS': { bg: '#dcfce7', color: '#166534' },
  'Postapproval Study Protocol': { bg: '#ede9fe', color: '#5b21b6' },
  'Postapproval Study Protocol - OSB': { bg: '#ede9fe', color: '#5b21b6' },
}

function ClearanceCard({ item }) {
  const [expanded, setExpanded] = useState(false)

  const reasonLabel = REASON_SHORT[item.supplement_reason] || item.supplement_reason || 'PMA Supplement'
  const reasonStyle = REASON_COLOR[item.supplement_reason] || { bg: '#f3f4f6', color: '#6b7280' }

  return (
    <div
      className="section"
      style={{ padding: '10px 14px', cursor: 'pointer', marginBottom: 8 }}
      onClick={() => setExpanded(e => !e)}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
            background: 'rgba(202,239,66,0.15)', color: '#4d6400', flexShrink: 0,
          }}>
            US 🇺🇸 FDA
          </span>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
            background: reasonStyle.bg, color: reasonStyle.color, flexShrink: 0,
          }}>
            {reasonLabel}
          </span>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4 }}>
            {item.title}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>{item.date}</span>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Clearance number + product code */}
      <div style={{ marginTop: 5, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {item.clearance_number && (
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
            {item.clearance_number}
          </span>
        )}
        {item.product_code && (
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
            PC: {item.product_code}
          </span>
        )}
        {item.supplement_type && (
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{item.supplement_type}</span>
        )}
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-dim)' }}
             onClick={e => e.stopPropagation()}>
          {item.description && (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
              {item.description}
            </p>
          )}
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Source: {item.source}</span>
            {item.url && (
              <a href={item.url} target="_blank" rel="noreferrer"
                 style={{ fontSize: 12, color: '#2563eb' }}>
                View on FDA →
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Clearance relevance filter ────────────────────────────────────────────────

function isRelevantClearance(item) {
  return item.is_clinical === true
}

// ── Coverage banner ───────────────────────────────────────────────────────────

function CoverageBanner() {
  return (
    <div style={{
      background: '#fffbeb', border: '1px solid #fde68a',
      borderRadius: 'var(--radius-md)', padding: '12px 16px', marginBottom: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#92400e', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
            Coverage Transparency — ~35%
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[
              { ok: true,  text: 'Clinical literature — PubMed systematic reviews, meta-analyses, RCTs (2,596 indexed)' },
              { ok: true,  text: 'New device clearances — FDA 510(k)s, CE marks, TGA approvals via Carver Feeds' },
              { ok: false, text: 'Comprehensive literature surveillance (Cochrane, Embase) — roadmap' },
              { ok: false, text: 'Clinical trial registries (ClinicalTrials.gov) — roadmap' },
            ].map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, fontSize: 12 }}>
                <span style={{ color: item.ok ? '#16a34a' : '#d97706', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>
                  {item.ok ? '✓' : '○'}
                </span>
                <span style={{ color: item.ok ? '#166534' : '#92400e', lineHeight: 1.4 }}>{item.text}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{
          background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 8,
          padding: '8px 12px', fontSize: 11, color: '#92400e', lineHeight: 1.5, maxWidth: 240,
        }}>
          <strong>Position:</strong> We track regulatory clearances that signal SotA shifts. Systematic literature monitoring is a separate pipeline — shown here for transparency.
        </div>
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

const TYPE_FILTERS = [
  { key: 'all',              label: 'All' },
  { key: 'systematic_review',label: 'Systematic Reviews' },
  { key: 'meta_analysis',    label: 'Meta-Analyses' },
  { key: 'rct',              label: 'RCTs' },
]

export default function Phase5() {
  const [tab, setTab]                   = useState('literature')
  const [typeFilter, setTypeFilter]     = useState('all')
  const [articles, setArticles]         = useState([])
  const [clearances, setClearances]     = useState([])
  const [stats, setStats]               = useState(null)
  const [meta, setMeta]                 = useState(null)
  const [loading, setLoading]           = useState(true)
  const [showAllClearances, setShowAllClearances] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetch('/data/sota_literature.json').then(r => r.json()),
      fetch('/data/sota_clearances.json').then(r => r.json()),
    ])
      .then(([lit, cl]) => {
        if (!cancelled) {
          setArticles(lit.articles || [])
          setStats(lit.stats)
          setMeta({ total: lit.total_indexed, relevant: lit.total_relevant, query: lit.search_query })
          setClearances(cl.clearances || [])
          setLoading(false)
        }
      })
      .catch(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const filteredArticles = typeFilter === 'all'
    ? articles
    : articles.filter(a => a.article_type_flags?.includes(typeFilter))

  return (
    <>
      {/* Page header */}
      <div style={{ marginBottom: 16 }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Tracks new clinical evidence and regulatory clearances that redefine the competitive and clinical benchmark landscape for cardiac monitoring devices.
        </p>
      </div>

      <CoverageBanner />

      {/* Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
          {tab === 'literature' ? 'Clinical Literature' : 'New Device Clearances'}
        </h3>
        <div className="tab-row" style={{ marginBottom: 0, borderBottom: 'none' }}>
          <div className={`tab${tab === 'literature' ? ' active' : ''}`}
               onClick={() => setTab('literature')}>
            Clinical Literature
            {stats && <span className="tab-badge" style={{ background: '#7c3aed' }}>{meta?.relevant}</span>}
          </div>
          <div className={`tab${tab === 'clearances' ? ' active' : ''}`}
               onClick={() => setTab('clearances')}>
            Device Clearances
            {clearances.length > 0 && (
              <span className="tab-badge">{clearances.filter(isRelevantClearance).length}</span>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-tertiary)', fontSize: 13 }}>
          Loading state-of-the-art data…
        </div>
      )}

      {/* ── CLINICAL LITERATURE TAB ── */}
      {!loading && tab === 'literature' && (
        <>
          {/* Stats row */}
          {stats && (
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              {[
                { label: 'Systematic Reviews', value: stats.systematic_review, color: '#7c3aed' },
                { label: 'Meta-Analyses',      value: stats.meta_analysis,     color: '#2563eb' },
                { label: 'RCTs',               value: stats.rct,               color: '#16a34a' },
                { label: 'Total Indexed',      value: meta?.total?.toLocaleString(), color: 'var(--text-primary)', sub: 'from PubMed search' },
              ].map(s => (
                <div key={s.label} className="stat-card">
                  <div className="stat-label">{s.label}</div>
                  <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
                  {s.sub && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{s.sub}</div>}
                </div>
              ))}
            </div>
          )}

          {/* Type filters */}
          <div className="filter-row section" style={{ marginBottom: 12, padding: '10px 14px' }}>
            <span className="filter-label">TYPE</span>
            {TYPE_FILTERS.map(f => {
              const count = f.key === 'all'
                ? articles.length
                : articles.filter(a => a.article_type_flags?.includes(f.key)).length
              return (
                <button key={f.key}
                  className={`filter-btn${typeFilter === f.key ? ' filter-btn--active' : ''}`}
                  onClick={() => setTypeFilter(f.key)}>
                  {f.label} <span className="filter-count">{count}</span>
                </button>
              )
            })}
          </div>

          {/* Article list */}
          {filteredArticles.length === 0 ? (
            <div className="empty-state">No articles match the selected filter.</div>
          ) : (
            <>
              {filteredArticles.map(a => <ArticleCard key={a.pmid} article={a} />)}
              <div style={{ marginTop: 8, textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
                Showing {filteredArticles.length} of {meta?.total?.toLocaleString()} indexed ·
                Filtered by cosine similarity to CardioWatch X1 clinical profile ·{' '}
                <a href="https://pubmed.ncbi.nlm.nih.gov" target="_blank" rel="noreferrer"
                   style={{ color: 'var(--accent-text)' }}>PubMed</a>
              </div>
            </>
          )}
        </>
      )}

      {/* ── DEVICE CLEARANCES TAB ── */}
      {!loading && tab === 'clearances' && (() => {
        const relevantClearances = clearances.filter(isRelevantClearance)
        const visibleClearances  = showAllClearances ? clearances : relevantClearances
        const hiddenCount        = clearances.length - relevantClearances.length

        return (
          <>
            <div style={{ marginBottom: 12, padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
              FDA PMA supplement activity for product code <strong>LWS</strong> (Implantable Cardioverter Defibrillator). Design/component changes and indication labeling updates are highlighted as clinically significant SotA signals — these may raise the clinical benchmark your CER must address.
            </div>

            {clearances.length === 0 ? (
              <div className="empty-state">No clearance signals found in current feed window.</div>
            ) : (
              <>
                {/* Filter bar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {showAllClearances
                      ? `Showing all ${clearances.length} clearances`
                      : `Showing ${relevantClearances.length} cardiac-relevant clearances`}
                    {!showAllClearances && hiddenCount > 0 && (
                      <span style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                        {' '}· {hiddenCount} unrelated hidden
                      </span>
                    )}
                  </div>
                  {hiddenCount > 0 && (
                    <button
                      onClick={() => setShowAllClearances(v => !v)}
                      style={{
                        fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 5,
                        border: '1px solid var(--border-dim)', background: 'var(--bg-secondary)',
                        color: 'var(--text-secondary)', cursor: 'pointer',
                      }}>
                      {showAllClearances ? `Show relevant only (${relevantClearances.length})` : `Show all (${clearances.length})`}
                    </button>
                  )}
                </div>

                {visibleClearances.length === 0 ? (
                  <div className="empty-state">No cardiac-relevant clearances found in current feed window.</div>
                ) : (
                  visibleClearances.map((item, i) => <ClearanceCard key={i} item={item} />)
                )}

                <div style={{ marginTop: 8, textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
                  {clearances.length} PMA records · FDA · Product code LWS
                </div>
              </>
            )}
          </>
        )
      })()}
    </>
  )
}
