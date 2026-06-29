// Panel 9 — Watch List. Counties with most votes outstanding + close 2020 margins.
import { num } from '../format'

export default function WatchList({ detail }) {
  const items = (detail?.watch_list || []).filter((c) => c.est_votes_remaining > 0)
  return (
    <div className="panel">
      <h2>Watch List — highest impact outstanding</h2>
      {items.length === 0 ? (
        <div className="empty">Nothing major outstanding (or no live data yet).</div>
      ) : (
        items.map((c) => {
          const m = c.margin_2020
          return (
            <div className="watch-item" key={c.county}>
              <div>
                <div className="c">{c.county}</div>
                <div className="sub">
                  2020 margin {m >= 0 ? 'D' : 'R'}+{num(Math.abs(m))} · {c.pct_reporting.toFixed(0)}% in
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="big" style={{ fontSize: 15 }}>{num(c.est_votes_remaining)}</div>
                <div className="sub">est. votes left</div>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
