import { useEffect, useMemo, useState } from 'react'
import { prepBaseline, projectAll, planReplay, replayAt, unitKey, SCENARIOS, BATCHES } from './model.js'
import { getDistrictLive } from '../api.js'

// Election-night district tracker.
//   Practice: replays 2026 in the browser (no backend), optionally with a swing.
//   Live:     polls /api/districts/live/{ST} (filled by the production poller).
const CHAMBERS = { house: 'State House', senate: 'State Senate' }
const SEATS = { GA: { house: 180, senate: 56 }, NC: { house: 120, senate: 50 }, SC: { house: 124, senate: 46 }, OH: { house: 99, senate: 33 } }
const POLL_MS = 30000

const num = (x) => (x == null ? '—' : Math.round(x).toLocaleString())
const mg = (m) => (m == null ? '—' : m >= 0 ? `D+${(m * 100).toFixed(1)}` : `R+${(-m * 100).toFixed(1)}`)
const pct = (x, d = 0) => (x == null ? '—' : `${(x * 100).toFixed(d)}%`)
const pts = (e) => (e == null ? '—' : `${e >= 0 ? '+' : '−'}${Math.abs(e * 100).toFixed(1)}`)
const winPct = (p, f) => (f < 0.999 && p > 0.99 ? '>99%' : f < 0.999 && p < 0.01 ? '<1%' : pct(p))
const mcls = (m) => (m == null ? 'muted' : m >= 0 ? 'd' : 'r')
const href = (...p) => '#/' + ['districts', ...p].join('/')

const baseCache = {}
function loadBase(st, ch) {
  const k = `${st}/${ch}`
  if (!baseCache[k]) {
    baseCache[k] = fetch(`/districts/${st}/baseline-${ch}.json`).then((r) => {
      if (!r.ok) throw new Error('Could not load the baseline')
      return r.json()
    })
  }
  return baseCache[k]
}

function usePins(st) {
  const key = `district-pins-${st}`
  const [pins, setPins] = useState(() => {
    try { return JSON.parse(localStorage.getItem(key) || '[]') } catch { return [] }
  })
  useEffect(() => {
    try { setPins(JSON.parse(localStorage.getItem(key) || '[]')) } catch { setPins([]) }
  }, [key])
  const toggle = (id) => setPins((p) => {
    const n = p.includes(id) ? p.filter((x) => x !== id) : [...p, id]
    try { localStorage.setItem(key, JSON.stringify(n)) } catch { /* private mode */ }
    return n
  })
  return [pins, toggle]
}

// live API payload -> model format for one chamber
function fromApi(payload, chamber) {
  const out = {}
  for (const [dist, x] of Object.entries(payload?.chambers?.[chamber] || {})) {
    const units = {}
    for (const [c, p, m, d, r, o, done] of x.units) units[unitKey(c, p, m)] = { d, r, o, done: !!done }
    out[dist] = { cands: x.cands, units }
  }
  return out
}

export default function LiveView({ st, chamber, district, summary }) {
  const [mode, setMode] = useState('practice')
  const [raw, setRaw] = useState(null)
  const [baseYear, setBaseYear] = useState(null)
  const [fullRaw, setFullRaw] = useState(null)
  const [err, setErr] = useState(null)
  const [scenario, setScenario] = useState('random')
  const [batch, setBatch] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [livePayload, setLivePayload] = useState(undefined) // undefined = not fetched, null = no live election
  const [liveErr, setLiveErr] = useState(null)
  const [pins, togglePin] = usePins(st)

  useEffect(() => {
    setRaw(null); setErr(null)
    loadBase(st, chamber).then((b) => {
      // staggered senates (OH): practice replays only the seats that were up in the latest election
      const dy = b.dist_year || {}
      setRaw(Object.fromEntries(Object.entries(b.districts).filter(([d]) => !dy[d] || dy[d] === b.year)))
      setFullRaw(b.districts)
      setBaseYear(b.year)
    }, (e) => setErr(e.message))
  }, [st, chamber])

  useEffect(() => { setBatch(0); setPlaying(false) }, [st, scenario])

  useEffect(() => {
    if (!playing) return
    if (batch >= BATCHES) { setPlaying(false); return }
    const id = setTimeout(() => setBatch((b) => Math.min(b + 1, BATCHES)), 1400)
    return () => clearTimeout(id)
  }, [playing, batch])

  useEffect(() => {
    if (mode !== 'live') return
    let alive = true
    const pull = () => getDistrictLive(st).then(
      (p) => { if (alive) { setLivePayload(p); setLiveErr(null) } },
      (e) => { if (alive) setLiveErr(e.message) })
    pull()
    const id = setInterval(pull, POLL_MS)
    return () => { alive = false; clearInterval(id) }
  }, [mode, st])

  // live: project only the seats on the ballot (those the feed reports); practice: the replayed seats
  const base = useMemo(() => {
    const src = mode === 'live' && livePayload ? fullRaw : raw
    if (!src) return null
    const up = mode === 'live' && livePayload ? livePayload.chambers?.[chamber] : null
    return Object.fromEntries(Object.entries(src)
      .filter(([d]) => !up || !Object.keys(up).length || up[d])
      .map(([d, r]) => [d, prepBaseline(r)]))
  }, [raw, fullRaw, mode, livePayload, chamber])
  const plan = useMemo(() => raw && planReplay(st, raw, scenario, 11), [raw, st, scenario])

  // real 2026 candidate names for practice mode
  const names = useMemo(() => {
    const m = {}
    for (const r of summary.districts) if (r.chamber === chamber && (r['2026'] || r['2024'])) m[r.district] = (r['2026'] || r['2024']).cands
    return m
  }, [summary, chamber])

  const live = useMemo(() => {
    if (!plan) return null
    if (mode === 'live') return livePayload ? fromApi(livePayload, chamber) : {}
    const snap = replayAt(plan, batch)
    for (const [d, x] of Object.entries(snap)) {
      const real = names[d] || []
      x.cands = x.cands.map((c) => ({ ...c, name: real.find((r) => r.party === c.party)?.name || c.name }))
    }
    return snap
  }, [plan, mode, batch, livePayload, chamber, names])

  const proj = useMemo(() => base && live && projectAll(base, live), [base, live])
  // seats not on the ballot this time (staggered senates) keep their current holder
  const hold = useMemo(() => {
    const h = { D: 0, R: 0, O: 0 }
    if (!proj) return h
    for (const r of summary.districts) {
      if (r.chamber !== chamber || proj.districts[r.district]) continue
      const y = r['2026'] || r['2024']
      if (y?.cands?.length) h[y.cands[0].party]++
    }
    return h
  }, [proj, summary, chamber])

  if (err) return <div className="err">{err}</div>
  if (!proj) return <div className="panel muted">Loading the baseline…</div>

  const controls = (
    <div className="panel live-controls">
      <div className="sim-row">
        <div className="toggle">
          <button className={mode === 'practice' ? 'on' : ''} onClick={() => setMode('practice')}>Practice: replay {baseYear || 'last election'}</button>
          <button className={mode === 'live' ? 'on' : ''} onClick={() => setMode('live')}>Live results</button>
        </div>
        {mode === 'practice' ? (
          <>
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {Object.entries(SCENARIOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <button onClick={() => { setBatch(0); setPlaying(false) }}>Reset</button>
            <button className="primary" disabled={batch >= BATCHES} onClick={() => setBatch((b) => b + 1)}>Next batch ▶</button>
            <button disabled={batch >= BATCHES} onClick={() => setPlaying((p) => !p)}>{playing ? 'Pause' : 'Auto-play'}</button>
            <span className="prog">Batch {batch}/{BATCHES}</span>
          </>
        ) : (
          <span className="muted small">
            {livePayload === undefined ? 'Checking for live results…'
              : livePayload === null ? 'No live election right now. Results appear here automatically on election night (refreshes every 30s).'
                : `${livePayload.election} · updated ${new Date(livePayload.as_of).toLocaleTimeString()} · refreshes every 30s`}
            {liveErr ? ` · ${liveErr}` : ''}
          </span>
        )}
      </div>
      {mode === 'practice' && <div className="progbar"><div style={{ width: `${(batch / BATCHES) * 100}%` }} /></div>}
      {mode === 'practice' && (
        <p className="muted small" style={{ margin: '8px 0 0' }}>
          Practice replays the real {baseYear} count in {BATCHES} batches{st === 'NC' ? ' (early and mail votes first, as NC reports them)' : ''}.
          Pick a scenario, then watch each district’s projection settle as precincts come in — the projection compares every
          counted precinct with the same precinct in {baseYear}.
        </p>
      )}
    </div>
  )

  return (
    <>
      {controls}
      {district
        ? <LiveDistrict baseYear={baseYear} st={st} chamber={chamber} x={proj.districts[district]} pinned={pins.includes(`${chamber}-${district}`)}
                        onPin={() => togglePin(`${chamber}-${district}`)} practice={mode === 'practice'} plan={plan} />
        : <LiveTable baseYear={baseYear} st={st} chamber={chamber} proj={proj} pins={pins} togglePin={togglePin} hold={hold}
                     practice={mode === 'practice'} plan={plan} batch={batch} />}
    </>
  )
}

// ----------------------------------------------------------------------------
function WinBar({ pD }) {
  return (
    <div className="winbar" title={`Democratic win chance ${pct(pD)}`}>
      <div className="seg-d" style={{ width: `${pD * 100}%` }} />
      <div className="seg-r" style={{ width: `${(1 - pD) * 100}%` }} />
    </div>
  )
}

function Status({ s }) {
  return <span className={`status ${s.tier} ${s.party === 'D' ? 'd' : s.party === 'R' ? 'r' : ''}`}>{s.label}</span>
}

function LiveTable({ baseYear, st, chamber, proj, pins, togglePin, practice, plan, batch, hold }) {
  const [sort, setSort] = useState('close')
  const [q, setQ] = useState('')
  const rows = Object.values(proj.districts)
  const seats = SEATS[st][chamber]
  const majority = Math.floor(seats / 2) + 1
  const projD = rows.filter((x) => x.status.party === 'D').length + hold.D
  const projO = rows.filter((x) => x.status.party === 'O').length + hold.O
  const held = hold.D + hold.R + hold.O
  const expD = rows.reduce((s, x) => s + x.pD, 0)
  const tossups = rows.filter((x) => x.status.tier === 'tossup').length
  const counted = rows.reduce((s, x) => s + x.counted.d + x.counted.r, 0)
  const expected = rows.reduce((s, x) => s + (x.reporting ? (x.counted.d + x.counted.r) / x.reporting : 0), 0)
  const anyCounted = counted > 0

  let list = rows
  const s = q.trim().toLowerCase()
  if (s) list = list.filter((x) => String(x.dist) === s || x.cands.some((c) => c.name?.toLowerCase().includes(s)) ||
    x.units.some((u) => u.county.toLowerCase().includes(s)))
  list = [...list].sort({
    close: (a, b) => (a.unopposed ? 9 : Math.abs(a.pD - 0.5)) - (b.unopposed ? 9 : Math.abs(b.pD - 0.5)),
    district: (a, b) => a.dist - b.dist,
    reporting: (a, b) => b.reporting - a.reporting,
    swing: (a, b) => (b.shift ?? 0) - (a.shift ?? 0),
  }[sort])
  const pinned = rows.filter((x) => pins.includes(`${chamber}-${x.dist}`))

  return (
    <>
      <div className="toolbar">
        <div className="toggle">
          {Object.entries(CHAMBERS).map(([k, v]) => (
            <button key={k} className={k === chamber ? 'on' : ''} onClick={() => { window.location.hash = href(st, 'live', k) }}>{v}</button>
          ))}
        </div>
        <div className="toggle">
          {Object.entries({ close: 'Closest first', district: 'By number', reporting: 'Most counted', swing: 'Biggest Dem swing' }).map(([k, v]) => (
            <button key={k} className={k === sort ? 'on' : ''} onClick={() => setSort(k)}>{v}</button>
          ))}
        </div>
        <div className="search"><input placeholder="District #, candidate or county…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      </div>

      <div className="cards">
        <div className="panel card">
          <div className="lbl">Projected seats · majority {majority}</div>
          <div className="big"><span className="d">{projD} D</span> · <span className="r">{seats - projD - projO} R</span>{projO ? <span className="muted"> · {projO} other</span> : null}</div>
          <div className="muted small">Expected Dem seats {(expD + hold.D).toFixed(1)} · {projD >= majority ? 'Dem majority' : 'Rep majority'} projected
            {held ? ` · incl. ${held} seats not up (${hold.D} D, ${hold.R} R)` : ''}</div>
        </div>
        <div className="panel card">
          <div className="lbl">Swing vs {baseYear} (counted precincts)</div>
          <div className={`big ${anyCounted ? mcls(proj.stateShift) : 'muted'}`}>{anyCounted ? `${pts(proj.stateShift * 2)} pts` : '—'}</div>
          <div className="muted small">{practice && batch === BATCHES ? `Scenario’s true swing: ${scenarioTruth(plan)}` : 'Change in Dem margin, same precincts'}</div>
        </div>
        <div className="panel card">
          <div className="lbl">Counted</div>
          <div className="big">{expected ? pct(counted / expected) : '0%'}</div>
          <div className="muted small">{num(counted)} votes · {tossups} toss-up {tossups === 1 ? 'seat' : 'seats'}</div>
        </div>
      </div>

      {pinned.length > 0 && (
        <div className="pins">
          {pinned.map((x) => (
            <a key={x.dist} className="panel pin-card" href={href(st, 'live', chamber, x.dist)}>
              <div className="lbl">★ {chamber === 'house' ? 'HD' : 'SD'}-{x.dist}</div>
              <div className={`big ${mcls(x.margin)}`}>{x.unopposed ? 'Unopposed' : mg(x.margin)}</div>
              <WinBar pD={x.pD} />
              <div className="muted small">{pct(x.reporting)} counted · <Status s={x.status} /></div>
            </a>
          ))}
        </div>
      )}

      <div className="panel scroll-x">
        <table className="dist-table">
          <thead><tr>
            <th title="Pin to the top">★</th><th className="lft">District</th><th>Counted</th><th>Now</th>
            <th>Projected</th><th className="lft">Dem win chance</th><th className="lft">Status</th><th title={`Dem margin change vs ${baseYear} in counted precincts`}>Swing</th>
          </tr></thead>
          <tbody>
            {list.map((x) => {
              const id = `${chamber}-${x.dist}`
              const lead = x.cands.slice().sort((a, b) => (b.votes || 0) - (a.votes || 0))
              return (
                <tr key={x.dist} className="click" onClick={() => { window.location.hash = href(st, 'live', chamber, x.dist) }}>
                  <td onClick={(e) => { e.stopPropagation(); togglePin(id) }} className={`star ${pins.includes(id) ? 'on' : ''}`}>{pins.includes(id) ? '★' : '☆'}</td>
                  <td className="lft"><b>{x.dist}</b> <span className="muted tiny">{lead.map((c) => c.name?.split(' ').slice(-1)[0]).filter(Boolean).join(' v ')}</span></td>
                  <td>{pct(x.reporting)}</td>
                  <td className={mcls(x.countedMargin)}>{!x.twoParty ? '—' : mg(x.countedMargin)}</td>
                  <td className={mcls(x.margin)}>{x.unopposed ? <span className="muted">unopposed</span> : !x.twoParty ? '—' : mg(x.margin)}</td>
                  <td className="lft"><WinBar pD={x.pD} /><span className="tiny muted">{!x.twoParty ? '' : winPct(x.pD, x.reporting)}</span></td>
                  <td className="lft"><Status s={x.status} /></td>
                  <td className={x.districtShift == null ? 'muted' : mcls(x.districtShift)}>{x.districtShift == null ? '—' : pts(x.districtShift * 2)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">
        “Now” = margin among votes counted so far. “Projected” fills in the uncounted precincts with their result from last time
        plus the swing seen in this district (blended with the statewide swing while few precincts are in).
        A winner is only “projected” once the chance is above 99.5% with at least half the expected vote counted.
      </p>
    </>
  )
}

function scenarioTruth(plan) {
  const v = Object.values(plan || {}).map((p) => p.trueSwing)
  if (!v.length) return '—'
  const avg = v.reduce((a, b) => a + b, 0) / v.length
  const spread = Math.max(...v) - Math.min(...v)
  return spread > 0.01 ? `${pts(avg)} pts on average, varying by district` : `${pts(avg)} pts`
}

// ----------------------------------------------------------------------------
function LiveDistrict({ baseYear, st, chamber, x, pinned, onPin, practice, plan }) {
  const [tab, setTab] = useState('in')
  if (!x) return <div className="panel muted">No such district.</div>
  const tot = x.counted.d + x.counted.r + x.counted.o || 1
  const counted = x.units.filter((u) => u.reported)
  const out = x.units.filter((u) => !u.done && !u.isNew)
  const remaining = out.reduce((s, u) => s + Math.max(u.exp2 - u.ld - u.lr, 0), 0)
  const remD = out.reduce((s, u) => s + (u.pd - u.ld), 0)
  const remShare = remaining ? remD / remaining : null
  const truth = practice ? plan?.[x.dist]?.trueSwing : null
  const cands = x.cands.slice().sort((a, b) => (b.votes || 0) - (a.votes || 0))
  const label = `${{ GA: 'Georgia', NC: 'North Carolina', SC: 'South Carolina', OH: 'Ohio' }[st]} ${CHAMBERS[chamber]} District ${x.dist}`

  return (
    <div className="detail">
      <div className="toolbar">
        <a className="back" href={href(st, 'live', chamber)}>← All {CHAMBERS[chamber]} districts</a>
        <button className={`pin-btn ${pinned ? 'on' : ''}`} onClick={onPin}>{pinned ? '★ Pinned' : '☆ Pin this district'}</button>
      </div>
      <h2 className="dist-title">{label}</h2>
      <div className="muted small">Bookmark this page to follow the district on election night.</div>

      <div className="panel votebar">
        <div className="names">
          {cands.map((c) => (
            <span key={c.party + c.name} className={c.party === 'D' ? 'd' : c.party === 'R' ? 'r' : 'muted'}>
              {c.name} ({c.party === 'D' ? 'Dem' : c.party === 'R' ? 'Rep' : 'Other'}) — {pct((c.votes || 0) / tot, 1)} · {num(c.votes)}
            </span>
          ))}
        </div>
        <div className="bar">
          <div className="seg-d" style={{ width: `${(x.counted.d / tot) * 100}%` }} />
          <div className="seg-o" style={{ width: `${(x.counted.o / tot) * 100}%` }} />
          <div className="seg-r" style={{ width: `${(x.counted.r / tot) * 100}%` }} />
        </div>
        <div className="totals"><span>{pct(x.reporting)} of the expected vote counted</span><span>{num(tot)} votes so far</span></div>
      </div>

      <div className="cards">
        <div className="panel card">
          <div className="lbl">Projected result</div>
          <div className={`big ${mcls(x.margin)}`}>{x.unopposed ? 'Unopposed' : !x.twoParty ? x.status.label : mg(x.margin)}</div>
          <Status s={x.status} />
        </div>
        <div className="panel card">
          <div className="lbl">Dem win chance</div>
          <div className="big">{!x.twoParty ? '—' : winPct(x.pD, x.reporting)}</div>
          <WinBar pD={x.pD} />
        </div>
        <div className="panel card">
          <div className="lbl">Swing vs {baseYear} here</div>
          <div className={`big ${x.districtShift == null ? 'muted' : mcls(x.districtShift)}`}>
            {x.districtShift == null ? 'none counted yet' : `${pts(x.districtShift * 2)} pts`}
          </div>
          <div className="muted small">
            Used in projection: {pts(x.shift * 2)} pts{truth != null ? ` · scenario truth ${pts(truth)}` : ''}
          </div>
        </div>
        <div className="panel card">
          <div className="lbl">Still to count</div>
          <div className="big">{num(remaining)}</div>
          <div className="muted small">{remShare == null ? 'Nothing left' : `Expected to break ${pct(remShare)} Dem`}</div>
        </div>
      </div>

      <div className="panel scroll-x">
        <div className="toolbar" style={{ marginBottom: 8 }}>
          <div className="toggle">
            <button className={tab === 'in' ? 'on' : ''} onClick={() => setTab('in')}>Counted ({counted.length})</button>
            <button className={tab === 'out' ? 'on' : ''} onClick={() => setTab('out')}>Still out ({out.length})</button>
          </div>
        </div>
        {tab === 'in' ? (
          <table className="dist-table">
            <thead><tr><th className="lft">Precinct</th><th>Method</th><th>Votes</th><th>Dem share now</th><th>{baseYear}</th><th>Change</th></tr></thead>
            <tbody>
              {counted.sort((a, b) => ((a.liveShare - (a.share ?? a.liveShare)) - (b.liveShare - (b.share ?? b.liveShare)))).map((u) => (
                <tr key={u.key}>
                  <td className="lft">{u.precinct}<span className="muted tiny"> · {cap(u.county)}{u.done ? '' : ' · partial'}{u.isNew ? ' · new' : ''}</span></td>
                  <td>{u.method === 'all' ? 'All' : u.method}</td>
                  <td>{num(u.ld + u.lr)}</td>
                  <td>{pct(u.liveShare, 1)}</td>
                  <td>{pct(u.share, 1)}</td>
                  <td className={u.share == null ? 'muted' : mcls(u.liveShare - u.share)}>{u.share == null ? '—' : pts((u.liveShare - u.share) * 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="dist-table">
            <thead><tr><th className="lft">Precinct</th><th>Method</th><th>Expected votes left</th><th>{baseYear} Dem share</th><th>Projected Dem share</th></tr></thead>
            <tbody>
              {out.sort((a, b) => (b.exp2 - b.ld - b.lr) - (a.exp2 - a.ld - a.lr)).map((u) => {
                const left = Math.max(u.exp2 - u.ld - u.lr, 0)
                return (
                  <tr key={u.key}>
                    <td className="lft">{u.precinct}<span className="muted tiny"> · {cap(u.county)}{u.reported ? ' · partial' : ''}</span></td>
                    <td>{u.method === 'all' ? 'All' : u.method}</td>
                    <td>{num(left)}</td>
                    <td className={mcls(u.share - 0.5)}>{pct(u.share, 1)}</td>
                    <td className={mcls((left ? (u.pd - u.ld) / left : u.share) - 0.5)}>{pct(left ? (u.pd - u.ld) / left : null, 1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
      <p className="muted tiny">
        {x.useLeg ? `Baseline = the ${baseYear} race for this seat, precinct by precinct.`
          : `This seat was uncontested last time, so the baseline is the top of the ticket (${baseYear === 2024 ? 'President' : 'US Senate'}) in the same precincts.`}
        {' '}Precincts that didn’t exist last time are counted but not projected.
      </p>
    </div>
  )
}

const cap = (s) => String(s).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
