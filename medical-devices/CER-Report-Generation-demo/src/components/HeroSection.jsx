const PILLARS = [
  {
    label: 'What',
    accent: '#4d6400',
    accentBg: 'rgba(202,239,66,0.18)',
    headline: 'Full lifecycle regulatory intelligence',
    body: 'From 510(k) and De Novo pre-market strategy through post-market surveillance and CER sign-off — across US, UK, and Switzerland in one view.',
  },
  {
    label: 'Why it matters',
    accent: '#d97706',
    accentBg: '#fef3c7',
    headline: 'Scattered data causes rejections',
    body: 'CERs fail because PMS signals are missed across jurisdictions, GMDN lookups are manual, and equivalent device analysis takes weeks. This closes that gap.',
  },
  {
    label: 'How',
    accent: '#16a34a',
    accentBg: '#dcfce7',
    headline: 'From keyword to report in minutes',
    body: 'Register keywords → query MAUDE, MHRA, Swissmedic → match equivalents via GMDN → score risk signals → export an audit-ready CER aligned to EU MDR + MEDDEV 2.7/1 rev.4.',
  },
]

export default function HeroSection() {
  return (
    <div className="hero-section">
      <div className="hero-headline">
        <p className="hero-so-what">
          Know your device's regulatory position — before regulators flag it for you.
        </p>
        <p className="hero-sub">
          Medical Device Lifecycle Platform covers every stage, every jurisdiction, every submission type.
        </p>
      </div>
      <div className="hero-pillars">
        {PILLARS.map(p => (
          <div key={p.label} className="hero-pillar">
            <div className="hero-pillar-label" style={{ background: p.accentBg, color: p.accent }}>
              {p.label}
            </div>
            <div className="hero-pillar-headline">{p.headline}</div>
            <div className="hero-pillar-body">{p.body}</div>
          </div>
        ))}
      </div>
    </div>
  )
}