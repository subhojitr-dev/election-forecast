// Panel 1 — Swing State Strip. Clickable cards across the top.
//
// Always renders every state the project has data for (`allStates`), not just
// the ones on the currently-selected election's ballot (`activeStates`) —
// states not on this ballot render as a grayed-out, unclickable placeholder
// instead of disappearing. Keeps the row visually stable across election
// switches instead of cards popping in/out, which read as a mismatch between
// the Election dropdown and what's shown here.
import { pct1, shiftLabel, leansDem } from '../format'

export default function SwingStateStrip({ allStates, activeStates, selected, onSelect }) {
  if (!allStates?.length) return <div className="strip" />
  const active = new Map((activeStates || []).map((s) => [s.state, s]))

  return (
    <div className="strip">
      {allStates.map((base) => {
        const s = active.get(base.state)
        if (!s) {
          return (
            <div key={base.state} className="state-card disabled">
              <div className="abbr">{base.state} <span className="ev">{base.ev} EV</span></div>
              <div className="not-ballot">Not on this ballot</div>
            </div>
          )
        }
        const dem = leansDem(s.win_prob_dem)
        const prob = dem ? s.win_prob_dem : 1 - s.win_prob_dem
        return (
          <div
            key={s.state}
            className={`state-card ${s.state === selected ? 'sel' : ''} ${dem ? 'lean-d' : 'lean-r'}`}
            onClick={() => onSelect(s.state)}
          >
            <div className="abbr">{s.state} <span className="ev">{s.ev} EV</span></div>
            <div className="prob">
              <span className={dem ? 'd' : 'r'}>{s.lean}</span> {pct1(prob)}
            </div>
            <div className="meta">{s.pct_reporting}% in · {shiftLabel(s.statewide_shift)} vs {s.baseline_year ?? '2020'}</div>
          </div>
        )
      })}
    </div>
  )
}
