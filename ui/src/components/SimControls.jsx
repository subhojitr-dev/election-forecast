// Election-night simulator controls: scenario picker + Next Batch stepper.
// (On real election day this is replaced by the live poller; same data path.)
export default function SimControls({ scenarios, scenario, onScenario, sim, onNext, onReset, busy }) {
  const pct = sim?.pct ?? 0
  const complete = sim?.complete
  return (
    <div className="sim panel">
      <div className="sim-row">
        <label className="muted" style={{ fontSize: 12 }}>Scenario</label>
        <select value={scenario} onChange={(e) => onScenario(e.target.value)} disabled={busy}>
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button onClick={onReset} disabled={busy}>Reset</button>
        <button className="primary" onClick={onNext} disabled={busy || complete}>
          {busy ? '…' : complete ? '✓ 100% in' : 'Next Batch ▶'}
        </button>
        <span className="prog">{pct}% reporting</span>
      </div>
      <div className="progbar"><div style={{ width: `${pct}%` }} /></div>
    </div>
  )
}
