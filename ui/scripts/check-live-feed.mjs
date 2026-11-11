// Feeds a stored live snapshot (from district_live_feed.py run against the finished
// 2026 election) through the model: every district must be 100% counted and its
// projected margin must equal the 2026 result exactly.
// Run: node scripts/check-live-feed.mjs <live_GA.json> GA
import { readFileSync } from 'node:fs'
import { prepBaseline, projectAll, unitKey } from '../src/districts/model.js'
const [file, st] = process.argv.slice(2)
const payload = JSON.parse(readFileSync(file))
const summary = JSON.parse(readFileSync(`public/districts/${st}.json`)).districts
let bad = 0, unmatched = 0, total = 0
for (const ch of ['house', 'senate']) {
  const raw = JSON.parse(readFileSync(`public/districts/${st}/baseline-${ch}.json`)).districts
  // only the seats on the ballot (staggered senates: OH)
  const base = Object.fromEntries(Object.entries(raw).filter(([d]) => payload.chambers[ch][d]).map(([d, r]) => [d, prepBaseline(r)]))
  const live = {}
  for (const [d, x] of Object.entries(payload.chambers[ch])) {
    const units = {}
    for (const [c, p, m, D, R, O, done] of x.units) units[unitKey(c, p, m)] = { d: D, r: R, o: O, done: !!done }
    live[d] = { cands: x.cands, units }
  }
  const P = projectAll(base, live).districts
  for (const [d, x] of Object.entries(P)) {
    total++
    unmatched += x.units.filter((u) => u.isNew).length
    const s = summary.find((r) => r.chamber === ch && r.district === +d)['2026']
    const ok = x.reporting > 0.999 && (!x.twoParty ? !s.contested && x.status.party === s.cands[0].party
      : Math.abs(x.margin - s.margin) < 0.0006)
    if (!ok) { bad++; if (bad < 6) console.log(ch, d, x.reporting, x.margin, s.margin, x.unopposed) }
  }
}
console.log(`${st}: ${total} districts, ${bad} mismatches, ${unmatched} live units not in baseline`)
