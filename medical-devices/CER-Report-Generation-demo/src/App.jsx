import { useState } from 'react'
import PhaseNav from './components/PhaseNav'
import Onboarding from './components/Onboarding'
import Phase1 from './components/Phase1'
import Phase2 from './components/Phase2'
import Phase3 from './components/Phase3'
import Phase4 from './components/Phase4'
import Phase5 from './components/Phase5'

export default function App() {
  const [ready, setReady]           = useState(false)
  const [activePhase, setActivePhase] = useState(0)

  return (
    <div className="container">
      <div className="header-bar">
        <div>
          <h2>Medical Device Lifecycle Platform</h2>
          <p>Post-market surveillance · CER generation · US / EU / AU / IN</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="tag tag-lime">Live</span>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>3 sources active</span>
        </div>
      </div>

      {!ready ? (
        <Onboarding onComplete={() => setReady(true)} />
      ) : (
        <>
          {/* Device context bar */}
          <div className="device-context-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#ffffff' }}>CardioWatch X1</span>
              <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>·</span>
              <span style={{ fontSize: 12, color: '#9ca3af', fontFamily: 'monospace' }}>510(k) K213456</span>
              <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>·</span>
              <span style={{ fontSize: 12, color: '#9ca3af' }}>Class IIb (EU) / Class II (US)</span>
              <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>·</span>
              <span style={{ fontSize: 12, color: '#9ca3af' }}>Markets: US · EU · AU · IN</span>
              <span style={{ fontSize: 12, color: '#4b5563', fontFamily: 'monospace' }}>·</span>
              <span style={{ fontSize: 12, color: '#f87171', fontWeight: 500 }}>CER Due: Aug 2026 (4 months)</span>
            </div>
            <div className="critical-alert-badge">
              <span className="critical-pulse" />
              2 CRITICAL
            </div>
          </div>

          <PhaseNav activePhase={activePhase} onSelect={setActivePhase} />

          {activePhase === 0 && <Phase1 />}
          {activePhase === 1 && <Phase2 />}
          {activePhase === 2 && <Phase5 />}
          {activePhase === 3 && <Phase3 />}
          {activePhase === 4 && <Phase4 />}
        </>
      )}
    </div>
  )
}
