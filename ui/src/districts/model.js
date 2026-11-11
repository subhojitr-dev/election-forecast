// Election-night district projection + the 2026 practice replay.
//
// Baseline (from ingestor/district_results.py): per district, one row per precinct
// x vote method:  [county, precinct, method, d, r, o, td, tr]   (2026 result)
//   d/r/o = legislative race, td/tr = top of ticket (US Senate) on the same ballots.
// Live (from the API, or from simulate() below): per district
//   { cands: [{name, party, votes}], units: { key: {d, r, o, done} } }
//   key = `${county}|${precinct}|${method}`, done = that unit is fully counted.
//
// Model, in plain terms:
//   1. Every fully counted unit is compared with the SAME unit in 2026 →
//      the district's swing (Dem two-party share, now minus 2026).
//   2. Early on, a district has few counted units, so its swing is blended with the
//      chamber-wide swing (weight K votes) instead of trusting a handful of precincts.
//   3. Units still out = what's counted so far + their remaining expected votes at
//      (2026 share + swing). Expected votes = 2026 votes x turnout ratio so far.
//   4. Win chance = normal CDF of projected margin / uncertainty; the uncertainty
//      shrinks as the counted share of the expected vote grows.

export const unitKey = (county, precinct, method) =>
  `${String(county).toUpperCase().trim()}|${String(precinct).toUpperCase().trim()}|${method}`

const K_POOL = 2500        // votes of district evidence worth as much as the statewide swing
const SD_START = 0.10      // margin uncertainty with nothing counted (10 pts)
const SD_FLOOR = 0.006     // never fully certain until the count is complete
const clamp = (x, a, b) => Math.max(a, Math.min(b, x))

// Abramowitz-Stegun normal CDF
export function phi(z) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z))
  const d = 0.3989423 * Math.exp(-z * z / 2)
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
  return z > 0 ? 1 - p : p
}

// Baseline rows -> per-unit {key, share, n2, n}
// Uses the 2026 legislative result where both parties ran, else the top of the ticket.
export function prepBaseline(rows) {
  const legD = rows.reduce((s, u) => s + u[3], 0)
  const legR = rows.reduce((s, u) => s + u[4], 0)
  const useLeg = legD > 0 && legR > 0
  const units = rows.map(([c, p, m, d, r, o, td, tr]) => {
    const D = useLeg ? d : td
    const R = useLeg ? r : tr
    return { key: unitKey(c, p, m), county: c, precinct: p, method: m, D, R,
      share: D + R ? D / (D + R) : null, n2: D + R, n: d + r + o }
  })
  return { useLeg, units }
}

// Core: project every district in a chamber.
//   base:  {dist: prepBaseline(...)}
//   live:  {dist: {cands, units}}
export function projectAll(base, live) {
  // pass 1 — per-district evidence
  const ev = {}
  let SW = 0, SS = 0, SN = 0, SV = 0
  for (const dist of Object.keys(base)) {
    const L = live[dist]
    let w = 0, s = 0, n = 0, v = 0
    // a one-party race says nothing about swing (its "share" is 100% or 0%)
    const contested = L && L.cands.some((c) => c.party === 'D') && L.cands.some((c) => c.party === 'R')
    if (contested) {
      for (const u of base[dist].units) {
        const lu = L.units[u.key]
        if (!lu || !lu.done || u.share == null || !u.n2) continue
        const l2 = lu.d + lu.r
        if (!l2) continue
        w += u.n2; s += u.n2 * (lu.d / l2 - u.share)
        n += u.n2; v += l2
      }
    }
    ev[dist] = { w, s: w ? s / w : 0, turnout: n ? v / n : null }
    SW += w; SS += s; SN += n; SV += v
  }
  const stateShift = SW ? SS / SW : 0
  const stateTurnout = SN ? SV / SN : 1

  // pass 2 — projections
  const out = {}
  for (const dist of Object.keys(base)) {
    const B = base[dist], L = live[dist], e = ev[dist]
    const shift = (e.w * e.s + K_POOL * stateShift) / (e.w + K_POOL)
    const tr = e.turnout ?? stateTurnout
    let D = 0, R = 0, cD = 0, cR = 0, cO = 0, expected = 0, counted = 0
    const units = []
    const seen = new Set()
    for (const u of B.units) {
      seen.add(u.key)
      const lu = L?.units[u.key]
      if (!u.n && !lu) continue   // no votes in this race here in 2026 → expect none now
      const ld = lu?.d || 0, lr = lu?.r || 0
      cD += ld; cR += lr; cO += lu?.o || 0
      const exp2 = Math.max(u.n2 * tr, ld + lr)
      let pd, pr
      if (lu?.done) { pd = ld; pr = lr }
      else {
        const rem = Math.max(exp2 - ld - lr, 0)
        const p = clamp((u.share ?? 0.5) + shift, 0.01, 0.99)
        pd = ld + rem * p; pr = lr + rem * (1 - p)
      }
      D += pd; R += pr
      expected += lu?.done ? ld + lr : exp2
      counted += ld + lr
      units.push({ ...u, ld, lr, done: !!lu?.done, reported: ld + lr > 0,
        liveShare: ld + lr ? ld / (ld + lr) : null, exp2, pd, pr })
    }
    // units in the live feed that weren't in 2026 (new / renamed precincts): count as-is
    if (L) for (const [k, lu] of Object.entries(L.units)) {
      if (seen.has(k) || !(lu.d + lu.r + (lu.o || 0))) continue
      D += lu.d; R += lu.r; cD += lu.d; cR += lu.r; cO += lu.o || 0
      expected += lu.d + lu.r; counted += lu.d + lu.r
      const [county, precinct, method] = k.split('|')
      units.push({ key: k, county, precinct, method, share: null, n2: 0, ld: lu.d, lr: lu.r, done: !!lu.done,
        reported: true, liveShare: lu.d + lu.r ? lu.d / (lu.d + lu.r) : null, pd: lu.d, pr: lu.r, isNew: true })
    }
    const f = expected ? clamp(counted / expected, 0, 1) : 0
    const margin = D + R ? (D - R) / (D + R) : 0
    const sd = f >= 0.999 ? 1e-4 : SD_START * (1 - f) + SD_FLOOR
    const cands = L?.cands || []
    const hasD = cands.some((c) => c.party === 'D'), hasR = cands.some((c) => c.party === 'R')
    let pD = sd ? phi(margin / sd) : margin > 0 ? 1 : 0
    let unopposed = null
    let status = null
    if (L && cands.length && !(hasD && hasR)) {
      if (cands.length === 1) {
        unopposed = cands[0].party
        pD = unopposed === 'D' ? 1 : 0
      } else {
        // e.g. Republican vs an unaffiliated candidate: no D-vs-R model, just the leader
        const lead = [...cands].sort((a, b) => (b.votes || 0) - (a.votes || 0))[0]
        pD = lead.party === 'D' ? 1 : 0
        status = { label: `${lead.party === 'O' ? 'Other' : lead.party} ${f >= 0.999 ? 'wins' : 'leads'} (no ${hasD ? 'Rep' : 'Dem'})`,
          party: lead.party, tier: f >= 0.999 ? 'call' : 'lean' }
      }
    }
    out[dist] = {
      dist: +dist, shift, districtShift: e.w ? e.s : null, evidence: e.w, turnout: tr,
      counted: { d: cD, r: cR, o: cO }, reporting: f, margin, pD, sd, unopposed,
      twoParty: !L || !cands.length || (hasD && hasR),
      countedMargin: cD + cR ? (cD - cR) / (cD + cR) : null,
      projected: { d: D, r: R }, cands, units, useLeg: B.useLeg,
      status: status || statusOf(pD, f, unopposed),
    }
  }
  return { districts: out, stateShift, stateTurnout }
}

export function statusOf(pD, f, unopposed) {
  if (unopposed) return { label: 'Unopposed', party: unopposed, tier: 'call' }
  const lead = pD >= 0.5 ? 'D' : 'R'
  const p = Math.max(pD, 1 - pD)
  if (f >= 0.999) return { label: `${lead} wins`, party: lead, tier: 'call' }
  if (p >= 0.995 && f >= 0.5) return { label: `${lead} projected`, party: lead, tier: 'call' }
  if (p >= 0.9) return { label: `Likely ${lead}`, party: lead, tier: 'likely' }
  if (p >= 0.7) return { label: `Lean ${lead}`, party: lead, tier: 'lean' }
  return { label: 'Toss-up', party: lead, tier: 'tossup' }
}

// ---------------------------------------------------------------------------
// Practice replay: re-runs 2026 from the baseline itself, batch by batch, with an
// optional swing so the model has something to discover.
//   scenario: 'actual' | 'dem3' | 'rep3' | 'random'
export const SCENARIOS = {
  actual: '2026 as it happened',
  dem3: 'Democrats 3 pts better everywhere',
  rep3: 'Republicans 3 pts better everywhere',
  random: 'Surprise: every district swings differently',
}
export const BATCHES = 10

function rng(seed) {
  let s = seed >>> 0
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 }
}

// Plan once per (state, chamber, scenario): when each unit reports, and its true result.
export function planReplay(st, rawBase, scenario, seed = 7) {
  const rand = rng(seed)
  const countySpeed = {}
  const dSwing = {}
  const plan = {}
  for (const [dist, rows] of Object.entries(rawBase)) {
    dSwing[dist] = scenario === 'dem3' ? 0.015 : scenario === 'rep3' ? -0.015
      : scenario === 'random' ? (rand() - 0.5) * 0.12 : 0       // share pts (margin = 2x)
    const legD = rows.reduce((s, u) => s + u[3], 0), legR = rows.reduce((s, u) => s + u[4], 0)
    const contested = legD > 0 && legR > 0
    plan[dist] = {
      cands: contested ? [{ name: 'Democrat', party: 'D' }, { name: 'Republican', party: 'R' }]
        : [{ name: legD ? 'Democrat' : legR ? 'Republican' : 'Other', party: legD ? 'D' : legR ? 'R' : 'O' }],
      units: rows.filter((u) => u[3] + u[4] + u[5] > 0).map(([c, p, m, d, r, o]) => {
        if (!(c in countySpeed)) countySpeed[c] = 0.4 + rand() * 1.2
        // reporting time 0..1: NC early/mail land right after polls close
        let t
        if (m === 'Early' || m === 'Mail') t = 0.02 + rand() * 0.12 / countySpeed[c]
        else if (m === 'Provisional') t = 0.97
        else t = clamp(0.1 + rand() * 0.85 / countySpeed[c], 0.1, 0.98)
        let D = d, R = r
        if (contested && d + r) {
          const sh = clamp(d / (d + r) + dSwing[dist] + (scenario === 'actual' ? 0 : (rand() - 0.5) * 0.04), 0.02, 0.98)
          D = Math.round((d + r) * sh); R = d + r - D
        }
        return { key: unitKey(c, p, m), t, partialAt: st === 'GA' && m === 'all' ? t * 0.6 : null, d: D, r: R, o }
      }),
      trueSwing: dSwing[dist] * 2,
    }
  }
  return plan
}

// Live snapshot after `batch` of BATCHES.
export function replayAt(plan, batch) {
  const T = batch / BATCHES
  const live = {}
  for (const [dist, P] of Object.entries(plan)) {
    const units = {}
    const tot = { d: 0, r: 0, o: 0 }
    for (const u of P.units) {
      let frac = 0
      if (T >= u.t || batch >= BATCHES) frac = 1
      else if (u.partialAt != null && T >= u.partialAt) frac = 0.6   // GA: advance votes first
      if (!frac) continue
      const x = { d: Math.round(u.d * frac), r: Math.round(u.r * frac), o: Math.round(u.o * frac), done: frac === 1 }
      units[u.key] = x
      tot.d += x.d; tot.r += x.r; tot.o += x.o
    }
    live[dist] = {
      cands: P.cands.map((c) => ({ ...c, votes: c.party === 'D' ? tot.d : c.party === 'R' ? tot.r : tot.o })),
      units,
    }
  }
  return live
}
