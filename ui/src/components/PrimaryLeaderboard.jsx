// The Democratic Senate primary is the actual contest being watched tonight —
// the Republican side isn't competitive, and mi_live_feed's ingest() is called
// with parties={"DEM"} so REP rows are never even pulled/stored (see
// production_poller.py's _mi_primary_poll). This shows the Democratic field's
// real standings, ranked by votes — not a D-vs-R head-to-head.
import { num, pct1 } from '../format'

export default function PrimaryLeaderboard({ candidates }) {
  const dem = candidates?.by_party?.DEM || []
  const byCounty = candidates?.by_county || []
  return (
    <>
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

      <div className="panel primary-by-county">
        <h2>By County ({byCounty.length} reporting)</h2>
        {byCounty.length === 0 ? (
          <div className="empty">No counties reporting yet.</div>
        ) : (
          <table className="primary-county-table">
            <thead>
              <tr>
                <th>County</th>
                <th>Leading</th>
                <th>Share</th>
                <th>Votes In</th>
              </tr>
            </thead>
            <tbody>
              {byCounty.map((c) => {
                const leader = c.candidates[0]
                return (
                  <tr key={c.county}>
                    <td>{c.county}</td>
                    <td>{leader?.candidate ?? '—'}</td>
                    <td>{leader ? pct1(leader.share) : '—'}</td>
                    <td>{num(c.total_votes)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
