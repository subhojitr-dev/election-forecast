// Panel 7 — County Breakdown table (+ Panel 3 search filter, passed in).
import { useState } from 'react'
import { num, pct1, shiftLabel } from '../format'

export default function CountyTable({ detail, search, onSelectCounty, selectedCounty }) {
  const [sortKey, setSortKey] = useState('live_total')
  const [asc, setAsc] = useState(false)
  const counties = detail?.counties || []

  const q = (search || '').trim().toUpperCase()
  let rows = q ? counties.filter((c) => c.county.includes(q)) : counties
  rows = [...rows].sort((a, b) => {
    const av = a[sortKey] ?? -Infinity, bv = b[sortKey] ?? -Infinity
    if (typeof av === 'string') return asc ? av.localeCompare(bv) : bv.localeCompare(av)
    return asc ? av - bv : bv - av
  })

  const sortBy = (k) => { if (k === sortKey) setAsc(!asc); else { setSortKey(k); setAsc(false) } }
  const Th = ({ k, children }) => <th onClick={() => sortBy(k)}>{children}{sortKey === k ? (asc ? ' ▲' : ' ▼') : ''}</th>

  return (
    <div className="panel">
      <h2>County Breakdown {q ? `· "${q}"` : ''} ({rows.length})</h2>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <Th k="county">County</Th>
              <Th k="pct_reporting">% Rep.</Th>
              <Th k="dem_share_live">D% Live</Th>
              <Th k="dem_share_2020">D% 2020</Th>
              <Th k="shift">vs Bench</Th>
              <Th k="turnout_vs_2020">Turn v20</Th>
              <Th k="pending_extrapolated">Pending</Th>
              <Th k="live_total">Votes In</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.county} onClick={() => onSelectCounty?.(c.county)}
                  className={`clickable${selectedCounty === c.county ? ' sel' : ''}`}>
                <td>{c.county}</td>
                <td>{c.pct_reporting.toFixed(0)}%</td>
                <td>{c.dem_share_live != null ? pct1(c.dem_share_live) : '—'}</td>
                <td className="muted">{pct1(c.dem_share_2020)}</td>
                <td className={c.shift == null ? 'muted' : c.shift >= 0 ? 'shift-pos' : 'shift-neg'}>
                  {shiftLabel(c.shift)}
                </td>
                <td className={c.turnout_vs_2020 == null ? 'muted' : c.turnout_vs_2020 >= 1 ? 'shift-pos' : 'shift-neg'}>
                  {c.turnout_vs_2020 != null ? `${((c.turnout_vs_2020 - 1) * 100).toFixed(0)}%` : '—'}
                </td>
                <td>{c.pending_extrapolated ? num(Math.round(c.pending_extrapolated)) : '—'}</td>
                <td>{num(c.live_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="empty">No counties match "{q}".</div>}
      </div>
    </div>
  )
}
