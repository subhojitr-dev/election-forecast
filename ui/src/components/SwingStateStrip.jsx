// Panel 1 — Swing State Strip. Clickable cards across the top.
import { pct1, shiftLabel, leansDem } from '../format'

export default function SwingStateStrip({ states, selected, onSelect }) {
  if (!states) return <div className="strip" />
  return (
    <div className="strip">
      {states.map((s) => {
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
            <div className="meta">{s.pct_reporting}% in · {shiftLabel(s.statewide_shift)} vs 2020</div>
          </div>
        )
      })}
    </div>
  )
}
