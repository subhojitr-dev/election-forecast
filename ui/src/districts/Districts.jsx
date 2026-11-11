import { useEffect, useMemo, useState } from 'react'
import './districts.css'
import LiveView from './LiveView.jsx'

// Static data built by ingestor/district_results.py → ui/public/districts/.
// No backend call: these pages load instantly even when the Render API is asleep.
const STATES = { GA: 'Georgia', NC: 'North Carolina', SC: 'South Carolina' }
const CHAMBERS = { house: 'State House', senate: 'State Senate' }
// Dem top-of-ticket candidate per year (Ossoff / Cooper / Harris…), stored in the data by the builder
const topNameOf = (data, year) => data?.top_names?.[String(year)] || TOP_RACE[year] || 'Top of ticket'
// most recent election available for a district row (SC Senate: 2024, plus a 2026 special)
const latestOf = (r) => r['2026'] || r['2024']
const latestYearOf = (r) => (r['2026'] ? '2026' : '2024')
const TOP_RACE = { 2026: 'US Senate', 2024: 'President' }

const cache = {}
async function load(path) {
  if (!cache[path]) {
    cache[path] = fetch(`/districts/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Could not load ${path}`)
      return r.json()
    })
  }
  return cache[path]
}

// ---------- formatting ----------
const num = (x) => (x == null ? '—' : Math.round(x).toLocaleString())
const mg = (m) => (m == null ? '—' : m >= 0 ? `D+${(m * 100).toFixed(1)}` : `R+${(-m * 100).toFixed(1)}`)
const pts = (e) => (e == null ? '—' : `${e >= 0 ? '+' : '−'}${Math.abs(e * 100).toFixed(1)}`)
const dshare = (d, r) => (d + r ? d / (d + r) : null)
const pct = (x) => (x == null ? '—' : `${(x * 100).toFixed(1)}%`)
const mcls = (m) => (m == null ? 'muted' : m >= 0 ? 'd' : 'r')
const PARTY = { D: 'Dem', R: 'Rep', O: 'Other' }
const winner = (y) => y?.cands?.[0]
const href = (...p) => '#/' + ['districts', ...p].join('/')

// Dem and Rep candidates (plus any other candidate who won or got 5%+), winner first
// and marked ✓ — so a losing Democrat is named, not just the winner.
function Candidates({ y }) {
  const tot = y.total || 1
  const shown = y.cands.filter((c) => c.party !== 'O' || c.win || c.votes / tot >= 0.05)
  const pick = []
  for (const p of ['D', 'R']) { const c = shown.find((x) => x.party === p); if (c) pick.push(c) }
  for (const c of shown) if (c.party === 'O') pick.push(c)
  pick.sort((a, b) => b.votes - a.votes)
  // within 1 pt: may still be in a recount (SC: automatic under 1%) — don't show a final ✓
  const close = y.contested && y.margin != null && Math.abs(y.margin) < 0.01
  return (
    <div className="cand-list">
      {pick.map((c) => (
        <div key={c.party + c.name} className={c.win ? 'cand win' : 'cand'}>
          <span className={`pill ${c.party === 'D' ? 'd' : c.party === 'R' ? 'r' : ''}`}>{PARTY[c.party]}</span>{' '}
          {c.win && !close ? '✓ ' : ''}{c.name}{c.inc ? <span className="muted tiny"> (inc.)</span> : null}
          {c.win && close ? <span className="flag">leads · within 1 pt</span> : null}
        </div>
      ))}
      {!y.cands.some((c) => c.party === 'D') && <div className="cand muted tiny">No Democrat ran</div>}
    </div>
  )
}

function Seg({ value, options, onChange }) {
  return (
    <div className="toggle">
      {Object.entries(options).map(([k, label]) => (
        <button key={k} className={String(value) === String(k) ? 'on' : ''} onClick={() => onChange(k)}>
          {label}
        </button>
      ))}
    </div>
  )
}

// ======================================================================
export default function Districts({ parts }) {
  const st = STATES[parts[0]?.toUpperCase()] ? parts[0].toUpperCase() : 'GA'
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    setData(null)
    load(`${st}.json`).then(setData, (e) => setErr(e.message))
  }, [st])

  const view = parts[1] === 'live' ? 'live' : parts[1] === 'targets' ? 'targets' : CHAMBERS[parts[1]] && parts[2] ? 'detail' : 'table'

  return (
    <div className="app districts">
      <header className="topbar">
        <h1>🗺️ Legislative Districts</h1>
        <span className="sub">Latest results for every State House &amp; Senate seat · compared with the top of the ticket and with the previous election</span>
      </header>

      <div className="toolbar dist-nav">
        <Seg value={st} options={STATES}
             onChange={(s) => { window.location.hash = href(s, ...(view === 'targets' || view === 'live' ? [view] : [])) }} />
        <Seg value={view === 'targets' || view === 'live' ? view : 'table'}
             options={{ table: 'Results', targets: '2028 targets', live: 'Election night' }}
             onChange={(v) => { window.location.hash = v === 'table' ? href(st) : href(st, v) }} />
      </div>

      {err && <div className="err">{err}</div>}
      {!data && !err && <div className="panel muted">Loading {STATES[st]}…</div>}
      {data && view === 'table' && <DistrictTable st={st} data={data} />}
      {data && view === 'targets' && <Targets st={st} data={data} />}
      {data && view === 'live' && <LiveView st={st} chamber={CHAMBERS[parts[2]] ? parts[2] : 'house'}
                                            district={parts[3] ? +parts[3] : null} summary={data} />}
      {data && view === 'detail' && <Detail st={st} chamber={parts[1]} district={+parts[2]} summary={data} />}

      {data && (
        <p className="foot muted">
          Source: {data.sources}. Built {data.built}.{' '}
          {data.notes.map((n) => <span key={n}>{n} </span>)}
          “Margin” = Dem minus Rep share of the two-party vote. “Edge” = the legislative Democrat’s margin
          minus the {TOP_RACE[2026]} margin on the same ballots — positive means they ran ahead of the top of the ticket.
        </p>
      )}
    </div>
  )
}

// ======================================================================
// All-districts table
const FILTERS = {
  all: 'All',
  close: 'Close (<10 pts)',
  flips: 'Changed party',
  uncontested: 'Uncontested',
}

function DistrictTable({ st, data }) {
  const [chamber, setChamber] = useState('house')
  const [year, setYear] = useState(String(data.latest?.house || 2026))
  const yearsFor = (ch) => (data.years || [2024, 2026]).map(String).filter((y) => data.districts.some((r) => r.chamber === ch && r[y]))
  const pickChamber = (ch) => { setChamber(ch); setYear(String(data.latest?.[ch] || 2026)) }
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState({ key: 'district', dir: 1 })
  const prev = year === '2026' ? '2024' : null
  const topName = topNameOf(data, year)

  const rows = useMemo(() => {
    let rs = data.districts.filter((r) => r.chamber === chamber && r[year])
    const s = q.trim().toLowerCase()
    if (s) {
      rs = rs.filter((r) => String(r.district) === s ||
        r[year].cands.some((c) => c.name.toLowerCase().includes(s)) ||
        r[year].counties.some((c) => c.toLowerCase().includes(s)))
    }
    if (filter === 'close') rs = rs.filter((r) => r[year].margin != null && Math.abs(r[year].margin) < 0.1)
    if (filter === 'uncontested') rs = rs.filter((r) => !r[year].contested)
    if (filter === 'flips') rs = rs.filter((r) => prev && r[prev] && winner(r[prev])?.party !== winner(r[year])?.party)
    const val = {
      district: (r) => r.district,
      margin: (r) => r[year].margin ?? (winner(r[year]).party === 'D' ? 2 : -2),
      top: (r) => r[year].top.margin,
      edge: (r) => r[year].edge ?? -9,
      swing: (r) => r.swing ?? -9,
      votes: (r) => r[year].total,
    }[sort.key]
    return [...rs].sort((a, b) => (val(a) - val(b)) * sort.dir)
  }, [data, chamber, year, filter, q, sort, prev])

  const all = data.districts.filter((r) => r.chamber === chamber && r[year])
  const seats = { D: 0, R: 0, O: 0 }
  all.forEach((r) => { seats[winner(r[year]).party]++ })
  const prevSeats = { D: 0, R: 0, O: 0 }
  if (prev) all.forEach((r) => r[prev] && prevSeats[winner(r[prev]).party]++)
  const contested = all.filter((r) => r[year].edge != null)
  const ahead = contested.filter((r) => r[year].edge > 0).length
  const uncD = all.filter((r) => !r[year].contested && winner(r[year]).party === 'D').length
  const uncR = all.filter((r) => !r[year].contested && winner(r[year]).party === 'R').length

  const th = (key, label, title) => (
    <th title={title} onClick={() => setSort((s) => ({ key, dir: s.key === key ? -s.dir : key === 'district' ? 1 : -1 }))}>
      {label}{sort.key === key ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}
    </th>
  )

  return (
    <>
      <div className="toolbar">
        <Seg value={chamber} options={CHAMBERS} onChange={pickChamber} />
        <Seg value={year} options={Object.fromEntries(yearsFor(chamber).reverse().map((y) => [y, y]))} onChange={setYear} />
        <Seg value={filter} options={FILTERS} onChange={setFilter} />
        <div className="search">
          <input placeholder="District #, candidate or county…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      <div className="cards">
        <div className="panel card">
          <div className="lbl">Seats won · {year}</div>
          <div className="big"><span className="d">{seats.D} D</span> · <span className="r">{seats.R} R</span>{seats.O ? <span className="muted"> · {seats.O} other</span> : null}</div>
          {prev && <div className="muted small">2024: {prevSeats.D} D · {prevSeats.R} R{prevSeats.O ? ` · ${prevSeats.O} other` : ''} ({seats.D - prevSeats.D >= 0 ? '+' : ''}{seats.D - prevSeats.D} D)</div>}
        </div>
        <div className="panel card">
          <div className="lbl">Ran ahead of {topName}</div>
          <div className="big">{ahead} <span className="muted small">of {contested.length} contested races</span></div>
          <div className="muted small">Same ballots, same district — a fair test of the candidate</div>
        </div>
        <div className="panel card">
          <div className="lbl">Uncontested</div>
          <div className="big"><span className="d">{uncD} D</span> · <span className="r">{uncR} R</span></div>
          <div className="muted small">Seats where only one major party ran</div>
        </div>
      </div>

      <div className="panel scroll-x">
        <table className="dist-table">
          <thead>
            <tr>
              {th('district', 'District')}
              <th className="lft">Candidates</th>
              {th('margin', 'Margin', 'Dem minus Rep, two-party')}
              {th('top', topName, `${TOP_RACE[year]} margin in this district`)}
              {th('edge', 'Edge', `Legislative margin minus ${topName}'s margin`)}
              {prev && th('swing', 'vs 2024', 'Change in legislative margin since 2024')}
              {th('votes', 'Votes')}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const y = r[year]
              const w = winner(y)
              const flipped = prev && r[prev] && winner(r[prev]).party !== w.party
              return (
                <tr key={r.district} onClick={() => { window.location.hash = href(st, chamber, r.district) }} className="click">
                  <td><b>{r.district}</b><div className="muted tiny">{y.counties.slice(0, 3).join(', ')}{y.counties.length > 3 ? ` +${y.counties.length - 3}` : ''}</div></td>
                  <td className="lft">
                    <Candidates y={y} />
                    {flipped && <span className="flag">flipped to {PARTY[w.party]}</span>}
                  </td>
                  <td className={mcls(y.margin)}>{y.contested ? mg(y.margin) : <span className="muted">uncontested</span>}</td>
                  <td className={mcls(y.top.margin)}>{mg(y.top.margin)}</td>
                  <td className={y.edge == null ? 'muted' : y.edge >= 0 ? 'ahead' : 'behind'}>{pts(y.edge)}</td>
                  {prev && <td className={r.swing == null ? 'muted' : r.swing >= 0 ? 'd' : 'r'}>{r.swing == null ? '—' : pts(r.swing)}</td>}
                  <td>{num(y.total)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {!rows.length && <div className="muted" style={{ padding: 12 }}>No districts match.</div>}
      </div>
    </>
  )
}

// ======================================================================
// 2028 targets — built from the 2026 result
function Targets({ st, data }) {
  const topName = [...new Set(data.districts.map((r) => topNameOf(data, latestYearOf(r))))].join(' / ')
  const groups = useMemo(() => {
    const rs = data.districts.filter((r) => latestOf(r))
    const L = latestOf
    const R = rs.filter((r) => winner(L(r)).party !== 'D')
    const D = rs.filter((r) => winner(L(r)).party === 'D')
    return {
      pickup: R.filter((r) => L(r).contested && L(r).margin > -0.1)
        .sort((a, b) => L(b).margin - L(a).margin),
      crossover: R.filter((r) => L(r).top.margin > 0)
        .sort((a, b) => L(b).top.margin - L(a).top.margin),
      noDem: R.filter((r) => !L(r).contested && L(r).top.margin > -0.2)
        .sort((a, b) => L(b).top.margin - L(a).top.margin),
      defend: D.filter((r) => (L(r).margin != null && L(r).margin < 0.08) || L(r).top.margin < 0.03)
        .sort((a, b) => (L(a).margin ?? L(a).top.margin) - (L(b).margin ?? L(b).top.margin)),
    }
  }, [data])

  const List = ({ title, blurb, rows, show }) => (
    <div className="panel">
      <h2>{title} <span className="count">{rows.length}</span></h2>
      <p className="muted small blurb">{blurb}</p>
      {rows.length ? (
        <table className="dist-table">
          <thead><tr><th>Seat</th><th className="lft">Latest candidates</th><th>Margin</th><th>{topName}</th><th>Edge</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const y = latestOf(r)
              return (
                <tr key={r.chamber + r.district} className="click"
                    onClick={() => { window.location.hash = href(st, r.chamber, r.district) }}>
                  <td><b>{r.chamber === 'house' ? 'HD' : 'SD'}-{r.district}</b><div className="muted tiny">{y.counties.slice(0, 2).join(', ')}</div></td>
                  <td className="lft"><Candidates y={y} /></td>
                  <td className={mcls(y.margin)}>{y.contested ? mg(y.margin) : <span className="muted">no opponent</span>}</td>
                  <td className={mcls(y.top.margin)}>{mg(y.top.margin)}</td>
                  <td className={y.edge == null ? 'muted' : y.edge >= 0 ? 'ahead' : 'behind'}>{pts(y.edge)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : <div className="muted small">None.</div>}
      {show}
    </div>
  )

  return (
    <div className="targets">
      <List title="Closest Republican holds" rows={groups.pickup}
            blurb="Republican-held after 2026, decided by less than 10 points. The first places to look for a pickup in 2028." />
      <List title={`${topName} won, Republican held`} rows={groups.crossover}
            blurb={`Voters here backed ${topName} but kept a Republican legislator. These show that the district can vote Democratic.`} />
      <List title="No Democrat on the ballot" rows={groups.noDem}
            blurb={`Republican-held seats with no Democratic candidate in 2026, where ${topName} got within 20 points. Recruiting targets.`} />
      <List title="Democratic seats to defend" rows={groups.defend}
            blurb={`Democratic-held seats won by less than 8 points, or where ${topName} was under 3 points ahead.`} />
    </div>
  )
}

// ======================================================================
// One district
function Detail({ st, chamber, district, summary }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [year, setYear] = useState(null)
  const [psort, setPsort] = useState({ key: 'edge', dir: 1 })
  useEffect(() => {
    setD(null); setErr(null)
    load(`${st}/${chamber}-${district}.json`).then(setD, (e) => setErr(e.message))
  }, [st, chamber, district])

  const row = summary.districts.find((r) => r.chamber === chamber && r.district === district)
  const yr = year || (d && (d['2026'] ? '2026' : '2024'))
  const y = d?.[yr]
  const topName = topNameOf(summary, yr)
  const title = `${STATES[st]} ${CHAMBERS[chamber]} District ${district}`

  const precincts = useMemo(() => {
    if (!y) return []
    const rs = y.precincts.map((p) => {
      const m = p.d + p.r ? (p.d - p.r) / (p.d + p.r) : null
      const tm = p.td + p.tr ? (p.td - p.tr) / (p.td + p.tr) : null
      return { ...p, m, tm, edge: y.contested && m != null && tm != null ? m - tm : null, votes: p.d + p.r + p.o }
    })
    const val = { precinct: (p) => p.county + p.precinct, m: (p) => p.m ?? -9, tm: (p) => p.tm ?? -9, edge: (p) => p.edge ?? 9, votes: (p) => p.votes }[psort.key]
    return rs.sort((a, b) => { const A = val(a), B = val(b); return (A < B ? -1 : A > B ? 1 : 0) * psort.dir })
  }, [y, psort])

  if (err) return <div className="err">{err}</div>
  if (!d) return <div className="panel muted">Loading {title}…</div>
  if (!y) return <div className="panel muted">No {yr} result for this district.</div>

  const w = y.cands[0]
  const D = y.cands.filter((c) => c.party === 'D')
  const R = y.cands.filter((c) => c.party === 'R')
  const tot = y.d + y.r + y.o || 1
  const pth = (key, label) => (
    <th onClick={() => setPsort((s) => ({ key, dir: s.key === key ? -s.dir : 1 }))}>{label}{psort.key === key ? (psort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>
  )

  return (
    <div className="detail">
      <div className="toolbar">
        <a className="back" href={href(st)}>← All {STATES[st]} districts</a>
        <Seg value={yr} options={Object.fromEntries(['2026', '2024'].filter((k) => d[k]).map((k) => [k, k]))} onChange={setYear} />
      </div>
      <h2 className="dist-title">{title}</h2>
      <div className="muted small">{y.counties.map((c) => c.county).join(' · ')}</div>

      <div className="panel votebar">
        <div className="names">
          {y.cands.slice(0, 3).map((c) => (
            <span key={c.name} className={c.party === 'D' ? 'd' : c.party === 'R' ? 'r' : 'muted'}>
              {c.win ? '✓ ' : ''}{c.name} ({PARTY[c.party]}{c.inc ? ', inc.' : ''}) — {pct(c.votes / tot)} · {num(c.votes)}
            </span>
          ))}
        </div>
        <div className="bar">
          {y.cands.map((c) => (
            <div key={c.name} className={c.party === 'D' ? 'seg-d' : c.party === 'R' ? 'seg-r' : 'seg-o'} style={{ width: `${(c.votes / tot) * 100}%` }} />
          ))}
        </div>
        {!y.contested && <div className="muted small" style={{ marginTop: 8 }}>
          {D.length ? 'No Republican' : R.length ? 'No Democrat' : 'Neither major party'} ran in this race.
        </div>}
      </div>

      <div className="cards">
        <div className="panel card">
          <div className="lbl">Result</div>
          <div className={`big ${mcls(y.margin)}`}>{y.contested ? mg(y.margin) : `${PARTY[w.party]}, unopposed`}</div>
          <div className="muted small">{num(y.total)} votes</div>
        </div>
        <div className="panel card">
          <div className="lbl">{topName} ({TOP_RACE[yr]}) here</div>
          <div className={`big ${mcls(y.top.margin)}`}>{mg(y.top.margin)}</div>
          <div className="muted small">{num(y.top.d)} D · {num(y.top.r)} R{y.est_share > 0.05 ? ' · partly estimated*' : ''}</div>
        </div>
        <div className="panel card">
          <div className="lbl">Edge vs {topName}</div>
          <div className={`big ${y.edge == null ? 'muted' : y.edge >= 0 ? 'ahead' : 'behind'}`}>
            {y.edge == null ? '—' : `${pts(y.edge)} pts`}
          </div>
          <div className="muted small">
            {y.edge == null ? 'Needs both parties on the ballot'
              : y.edge >= 0 ? `The Democrat ran ahead of ${topName}` : `The Democrat ran behind ${topName}`}
          </div>
        </div>
        {yr === '2026' && row?.['2024'] && (
          <div className="panel card">
            <div className="lbl">Since 2024</div>
            <div className={`big ${row.swing == null ? 'muted' : mcls(row.swing)}`}>{row.swing == null ? '—' : `${pts(row.swing)} pts`}</div>
            <div className="muted small">
              2024: {row['2024'].contested ? mg(row['2024'].margin) : 'uncontested'} · {topNameOf(summary, 2024)} {mg(row['2024'].top.margin)}
            </div>
          </div>
        )}
      </div>

      <div className="grid2">
        <div className="panel">
          <h2>By vote method</h2>
          <table>
            <thead><tr><th>Method</th><th>Votes</th><th>Dem share</th>{y.methods.some((m) => m.td != null) && <th>{topName}</th>}</tr></thead>
            <tbody>
              {y.methods.map((m) => (
                <tr key={m.method}>
                  <td>{m.method}</td>
                  <td>{num(m.d + m.r)}</td>
                  <td>{pct(dshare(m.d, m.r))}</td>
                  {y.methods.some((x) => x.td != null) && <td>{m.td == null ? '—' : pct(dshare(m.td, m.tr))}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted tiny">Two-party (Dem vs Rep) votes in the legislative race.</p>
        </div>
        <div className="panel">
          <h2>By county</h2>
          <table>
            <thead><tr><th>County</th><th>Votes</th><th>Dem share</th><th>{topName}</th><th>Edge</th></tr></thead>
            <tbody>
              {y.counties.map((c) => {
                const m = c.d + c.r ? (c.d - c.r) / (c.d + c.r) : null
                const tm = c.td + c.tr ? (c.td - c.tr) / (c.td + c.tr) : null
                const e = y.contested && m != null && tm != null ? m - tm : null
                return (
                  <tr key={c.county}>
                    <td>{c.county}</td><td>{num(c.d + c.r + c.o)}</td>
                    <td>{pct(dshare(c.d, c.r))}</td><td>{pct(dshare(c.td, c.tr))}</td>
                    <td className={e == null ? 'muted' : e >= 0 ? 'ahead' : 'behind'}>{pts(e)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel scroll-x">
        <h2>Precincts <span className="count">{precincts.length}</span></h2>
        <p className="muted small blurb">
          {y.contested
            ? `Sorted by edge — the precincts where the Democrat ran furthest behind ${topName} are at the top. Click a column to re-sort.`
            : 'Uncontested race — shown for turnout and top-of-ticket lean only.'}
          {st === 'NC' && yr === '2026' ? ' NC precinct rows include Election Day votes only for now; early and mail votes appear in the totals above.' : ''}
        </p>
        <table className="dist-table">
          <thead><tr>{pth('precinct', 'Precinct')}{pth('votes', 'Votes')}{pth('m', 'Dem margin')}{pth('tm', topName)}{pth('edge', 'Edge')}</tr></thead>
          <tbody>
            {precincts.map((p) => (
              <tr key={p.county + p.precinct}>
                <td>{p.precinct}<span className="muted tiny"> · {p.county}</span></td>
                <td>{num(p.votes)}</td>
                <td className={mcls(p.m)}>{y.contested ? mg(p.m) : '—'}</td>
                <td className={mcls(p.tm)}>{mg(p.tm)}</td>
                <td className={p.edge == null ? 'muted' : p.edge >= 0 ? 'ahead' : 'behind'}>{pts(p.edge)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {y.est_share > 0.05 && (
        <p className="muted tiny">* {Math.round(y.est_share * 100)}% of this district’s {TOP_RACE[yr]} votes were cast early or by mail in a county with several districts and are reported county-wide. Their split between districts is estimated from each district’s Election Day lean until the State Board posts precinct-sorted results.</p>
      )}
    </div>
  )
}
