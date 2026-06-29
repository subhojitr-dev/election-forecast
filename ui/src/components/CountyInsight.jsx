// County Insight — plain-English note box + ballot-type (mode) selector.
// Shows the selected county's analysis (turnout vs 2020 benchmark, pending vote
// and which way it leans) plus a per-ballot-type breakdown. With no county
// selected it shows the statewide ballot-type status.
import { useEffect, useState } from 'react'
import { getCountyDetail } from '../api'
import { num, pct1 } from '../format'

const MODE_LABEL = {
  all: 'All', election_day: 'Election-Day', early: 'Early', mail: 'Mail', military: 'Military',
}
const TABS = ['all', 'election_day', 'early', 'mail', 'military']

export default function CountyInsight({ detail, race, election, selectedCounty }) {
  const [cty, setCty] = useState(null)
  const [mode, setMode] = useState('all')

  useEffect(() => {
    let alive = true
    if (selectedCounty && detail?.state) {
      getCountyDetail(detail.state, selectedCounty, race, election)
        .then((d) => { if (alive) setCty(d) })
        .catch(() => { if (alive) setCty(null) })
    } else {
      setCty(null)
    }
    return () => { alive = false }
  }, [selectedCounty, detail?.state, race, election, detail?.pct_reporting])

  const modes = (cty?.modes && cty.modes.length ? cty.modes : detail?.modes) || []

  return (
    <div className="panel">
      <h2>County Insight {selectedCounty ? `· ${selectedCounty}` : '· statewide'}</h2>

      {cty ? (
        <div className="note-box">{cty.note}</div>
      ) : (
        <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
          Click a county in the table below to see its analysis. Showing{' '}
          {detail?.name || 'statewide'} ballot-type status:
        </div>
      )}

      <div className="toggle bucket-tabs">
        {TABS.map((m) => (
          <button key={m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>
            {MODE_LABEL[m]}
          </button>
        ))}
      </div>

      <BucketStatus modes={modes} mode={mode} />
    </div>
  )
}

function BucketStatus({ modes, mode }) {
  if (mode === 'all') {
    const specific = modes.filter((m) => m.mode !== 'all')
    const rows = specific.length ? specific : modes
    if (!rows.length || !rows.some((m) => m.total)) return <div className="empty">No votes counted yet.</div>
    return (
      <table className="bucket-table">
        <thead><tr><th>Ballot type</th><th>Votes counted</th><th>Dem 2-pty</th></tr></thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.mode}>
              <td>{MODE_LABEL[m.mode] || m.mode}</td>
              <td>{num(m.total)}</td>
              <td className={m.dem_share_2pty == null ? 'muted' : m.dem_share_2pty >= 0.5 ? 'shift-pos' : 'shift-neg'}>
                {m.dem_share_2pty != null ? pct1(m.dem_share_2pty) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }
  const m = modes.find((x) => x.mode === mode)
  if (!m || !m.total) return <div className="empty">No {MODE_LABEL[mode]} votes counted yet.</div>
  const d = m.dem_share_2pty
  return (
    <div className="bucket-detail">
      <div><b>{num(m.total)}</b> {MODE_LABEL[mode]} votes counted</div>
      <div className="muted">
        Dem <span className={d >= 0.5 ? 'shift-pos' : 'shift-neg'}>{d != null ? pct1(d) : '—'}</span>
        {' · '}Rep {d != null ? pct1(1 - d) : '—'}
      </div>
    </div>
  )
}
