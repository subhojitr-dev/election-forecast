// Shows a primary's live standings — one or more separate intra-party fields,
// not a D-vs-R head-to-head. Originally built MI-only (Democratic field only,
// since mi_live_feed's ingest() only ever pulls parties={"DEM"} — the GOP side
// wasn't competitive). Generalized for GA's Governor primary, which has real,
// separately-contested Dem AND Rep fields — so this renders whichever parties
// are actually present in `by_party`, not just DEM.
import { num, pct1 } from '../format'

const PARTY_ORDER = ['DEM', 'REP']
const PARTY_LABEL = { DEM: 'Democratic', REP: 'Republican' }

function orderedParties(byParty) {
  const keys = Object.keys(byParty || {})
  return keys.sort((a, b) => {
    const ia = PARTY_ORDER.indexOf(a), ib = PARTY_ORDER.indexOf(b)
    if (ia === -1 && ib === -1) return a.localeCompare(b)
    if (ia === -1) return 1
    if (ib === -1) return -1
    return ia - ib
  })
}

export default function PrimaryLeaderboard({ candidates, title }) {
  const byParty = candidates?.by_party || {}
  const parties = orderedParties(byParty)
  const byCounty = candidates?.by_county || []

  return (
    <>
      <div className="panel primary-leaderboard">
        <h2>{title || 'Primary — Live Standings'}</h2>
        {parties.length === 0 ? (
          <div className="empty">No votes reported yet.</div>
        ) : (
          <div className="primary-fields">
            {parties.map((party) => {
              const field = byParty[party] || []
              return (
                <div key={party} className="primary-field">
                  <h3 className={party === 'DEM' ? 'd' : party === 'REP' ? 'r' : ''}>
                    {PARTY_LABEL[party] || party} field
                  </h3>
                  {field.length === 0 ? (
                    <div className="empty">No votes reported yet.</div>
                  ) : (
                    <ol className="primary-list">
                      {field.map((c, i) => (
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
            })}
          </div>
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
                {parties.map((p) => <th key={p}>Leading {PARTY_LABEL[p] || p}</th>)}
                <th>Votes In</th>
              </tr>
            </thead>
            <tbody>
              {byCounty.map((c) => {
                // Each party's own leader + share, computed within that party's
                // own field — not diluted by the other party's vote count.
                const leaders = parties.map((p) => {
                  const inParty = c.candidates.filter((x) => x.party === p)
                  const partyTotal = inParty.reduce((s, x) => s + x.votes, 0) || 1
                  const top = inParty[0]
                  return top ? { ...top, share: top.votes / partyTotal } : null
                })
                return (
                  <tr key={c.county}>
                    <td>{c.county}</td>
                    {leaders.map((leader, i) => (
                      <td key={parties[i]}>
                        {leader ? `${leader.candidate} · ${pct1(leader.share)}` : '—'}
                      </td>
                    ))}
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
