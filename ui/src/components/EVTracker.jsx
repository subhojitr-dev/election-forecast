// Panel 10 — Electoral Vote Tracker. Mini scoreboard of all 7+1 swing states.
import { pct1, shiftLabel, leansDem } from '../format'

export default function EVTracker({ data, selected, onSelect }) {
  if (!data) return null
  const { ev_leaning, states } = data
  const totalEV = (ev_leaning?.dem || 0) + (ev_leaning?.rep || 0)
  const demPct = totalEV ? (ev_leaning.dem / totalEV) * 100 : 50
  return (
    <div className="panel">
      <h2>Swing-State EV Tracker</h2>
      <div className="ev-total">
        <span className="d">D {ev_leaning?.dem ?? 0}</span>
        <span className="r">{ev_leaning?.rep ?? 0} R</span>
      </div>
      <div className="ev-bar"><div className="dseg" style={{ width: `${demPct}%` }} /></div>
      <div style={{ marginTop: 10 }}>
        {states.map((s) => {
          const dem = leansDem(s.win_prob_dem)
          return (
            <div className="ev-item" key={s.state} onClick={() => onSelect(s.state)}
                 style={s.state === selected ? { color: 'var(--accent)' } : undefined}>
              <span className="c">{s.state} <span className="muted">{s.ev} EV</span></span>
              <span>
                <span className={dem ? 'd' : 'r'}>{s.lean}</span>{' '}
                <span className="muted">{shiftLabel(s.statewide_shift)}</span>
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
