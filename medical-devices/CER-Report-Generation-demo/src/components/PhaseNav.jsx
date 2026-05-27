const PHASES = [
  { num: 'Phase 1', label: 'Intelligence Feed'  },
  { num: 'Phase 2', label: 'Similar Devices'    },
  { num: 'Phase 3', label: 'State of the Art'   },
  { num: 'Phase 4', label: 'Regulatory Horizon' },
  { num: 'Phase 5', label: 'CER Readiness'      },
]

export default function PhaseNav({ activePhase, onSelect }) {
  return (
    <div className="phase-nav">
      {PHASES.map((p, i) => (
        <button
          key={i}
          className={`phase-btn${activePhase === i ? ' active' : ''}`}
          onClick={() => onSelect(i)}
        >
          <span className="num">{p.num}</span>
          {p.label}
        </button>
      ))}
    </div>
  )
}
