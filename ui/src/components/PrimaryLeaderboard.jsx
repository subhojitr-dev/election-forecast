// The Democratic Senate primary is the actual contest being watched tonight —
// the Republican side isn't competitive, and mi_live_feed's ingest() is called
// with parties={"DEM"} so REP rows are never even pulled/stored (see
// production_poller.py's _mi_primary_poll). This shows the Democratic field's
// real standings, ranked by votes — not a D-vs-R head-to-head.
import { num, pct1 } from '../format'

export default function PrimaryLeaderboard({ candidates }) {
  const dem = candidates?.by_party?.DEM || []
  return (
    <div className="panel primary-leaderboard">
      <h2>Michigan Democratic Senate Primary — Live Standings</h2>
      {dem.length === 0 ? (
        <div className="empty">No votes reported yet.</div>
      ) : (
        <ol className="primary-list">
          {dem.map((c, i) => (
            <li key={c.candidate} className={i === 0 ? 'leading' : ''}>
              <span className="cand-name">{c.candidate}</span>
              <span className="cand-share">{pct1(c.share)}</span>
              <span className="cand-votes">{num(c.votes)} votes</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
