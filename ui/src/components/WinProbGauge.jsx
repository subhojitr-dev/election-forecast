// Panel 6 — Win Probability Gauge (hand-drawn SVG semicircle + needle).
import { pct1, leansDem } from '../format'

// polar point on the gauge arc; theta in degrees (180=left, 90=top, 0=right)
function pt(cx, cy, r, deg) {
  const t = (deg * Math.PI) / 180
  return [cx + r * Math.cos(t), cy - r * Math.sin(t)]
}
function arc(cx, cy, r, a0, a1) {
  const [x0, y0] = pt(cx, cy, r, a0)
  const [x1, y1] = pt(cx, cy, r, a1)
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0
  // sweep flag 0 because angles decrease as we go left->right with this convention
  return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`
}

export default function WinProbGauge({ detail }) {
  const prob = detail?.win_prob_dem ?? 0.5     // P(Dem wins)
  const dem = leansDem(prob)
  const cx = 130, cy = 125, r = 100
  const needle = pt(cx, cy, r - 14, 180 * prob)  // high D prob -> points left

  return (
    <div className="panel gauge">
      <h2>Win Probability</h2>
      <svg viewBox="0 0 260 150" width="100%" style={{ maxWidth: 260 }}>
        {/* red right half, blue left half */}
        <path d={arc(cx, cy, r, 90, 0)} stroke="var(--rep)" strokeWidth="18" fill="none" />
        <path d={arc(cx, cy, r, 180, 90)} stroke="var(--dem)" strokeWidth="18" fill="none" />
        {/* needle */}
        <line x1={cx} y1={cy} x2={needle[0]} y2={needle[1]} stroke="var(--text)" strokeWidth="3" />
        <circle cx={cx} cy={cy} r="6" fill="var(--text)" />
        <text x="18" y="145" fill="var(--dem)" fontSize="11">DEM</text>
        <text x="225" y="145" fill="var(--rep)" fontSize="11">REP</text>
      </svg>
      <div className="label">
        <span className={dem ? 'd' : 'r'}>{detail?.lean || '—'}</span>
        {' · '}
        <span className={dem ? 'd' : 'r'}>{pct1(dem ? prob : 1 - prob)}</span>
      </div>
      <div className="tier">{detail?.confidence_tier || ''}</div>
    </div>
  )
}
