// Panel 4 — Live Vote Bar. Candidate totals, percentages, margin, blue/red split.
import { num, pct1 } from '../format'

export default function LiveVoteBar({ detail }) {
  const d = detail?.dem_votes || 0
  const r = detail?.rep_votes || 0
  const tot = d + r
  if (tot === 0) {
    return (
      <div className="panel votebar">
        <h2>Live Vote</h2>
        <div className="empty">No votes reported yet — showing pre-election outlook.</div>
      </div>
    )
  }
  const dShare = d / tot
  const demName = detail.dem_candidate || 'Democrat'
  const repName = detail.rep_candidate || 'Republican'
  const margin = Math.abs(d - r)
  const leadD = d >= r
  return (
    <div className="panel votebar">
      <h2>Live Vote · {Math.round(detail.pct_reporting)}% reporting</h2>
      <div className="names">
        <span className="d">{demName}</span>
        <span className="r">{repName}</span>
      </div>
      <div className="bar">
        <div className="seg-d" style={{ width: `${dShare * 100}%` }} />
        <div className="seg-r" style={{ width: `${(1 - dShare) * 100}%` }} />
      </div>
      <div className="totals">
        <span className="d big">{pct1(dShare)}</span>
        <span className="r big">{pct1(1 - dShare)}</span>
      </div>
      <div className="totals">
        <span>{num(d)} votes</span>
        <span>{num(r)} votes</span>
      </div>
      <div style={{ textAlign: 'center', marginTop: 8 }}>
        <span className={leadD ? 'd' : 'r'}>
          {leadD ? demName : repName} leads by {num(margin)}
        </span>
      </div>
    </div>
  )
}
