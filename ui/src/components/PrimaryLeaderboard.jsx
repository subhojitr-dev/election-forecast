// A primary is two SEPARATE intra-party contests, not a D-vs-R head-to-head — so
// unlike LiveVoteBar (which shows one leading Dem vs one leading Rep as if they're
// competing), this shows each party's full candidate field, ranked by votes, so
// you can actually watch who's winning the Democratic primary and who's winning
// the Republican primary.
import { num, pct1 } from '../format'

function PartyColumn({ label, cssClass, candidates }) {
  return (
    <div className="primary-col">
      <h3 className={cssClass}>{label}</h3>
      {(!candidates || candidates.length === 0) ? (
        <div className="empty">No votes reported yet.</div>
      ) : (
        <ol className="primary-list">
          {candidates.map((c, i) => (
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

export default function PrimaryLeaderboard({ candidates }) {
  const byParty = candidates?.by_party || {}
  return (
    <div className="panel primary-leaderboard">
      <h2>Primary Standings — each party's own contest</h2>
      <div className="primary-cols">
        <PartyColumn label="Democratic Primary" cssClass="d" candidates={byParty.DEM} />
        <PartyColumn label="Republican Primary" cssClass="r" candidates={byParty.REP} />
      </div>
    </div>
  )
}
