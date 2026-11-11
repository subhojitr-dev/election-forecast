// Replays 2026 under each scenario and checks the district projections:
// error vs the true final margin by batch, wrong calls, and calibration.
// Run: node scripts/calibrate-districts.mjs
import { readFileSync } from 'node:fs'
import { prepBaseline, projectAll, planReplay, replayAt, SCENARIOS, BATCHES } from '../src/districts/model.js'

let bad = 0
for (const st of ['GA', 'NC', 'SC', 'OH', 'TX']) for (const ch of ['house', 'senate']) {
  const raw = JSON.parse(readFileSync(`public/districts/${st}/baseline-${ch}.json`)).districts
  const base = Object.fromEntries(Object.entries(raw).map(([d, r]) => [d, prepBaseline(r)]))
  for (const sc of Object.keys(SCENARIOS)) for (const seed of [1, 2, 3]) {
    const plan = planReplay(st, raw, sc, seed)
    const fin = projectAll(base, replayAt(plan, BATCHES)).districts
    const rows = []
    for (let b = 1; b <= BATCHES; b++) {
      const P = projectAll(base, replayAt(plan, b)).districts
      let err = 0, n = 0, wrong = 0, confWrong = 0, rep = 0
      for (const [d, x] of Object.entries(P)) {
        if (x.unopposed) continue
        const truth = fin[d].margin
        err += Math.abs(x.margin - truth); n++; rep += x.reporting
        const call = x.pD >= 0.5 ? 1 : -1
        if (call !== Math.sign(truth)) { wrong++; if (Math.max(x.pD, 1 - x.pD) >= 0.9) confWrong++ }
        if (x.status.tier === 'call' && call !== Math.sign(truth)) bad++
      }
      rows.push(`b${b} rep ${(100 * rep / n).toFixed(0)}% err ${(100 * err / n).toFixed(2)} wrong ${wrong} (≥90%: ${confWrong})`)
    }
    if (seed === 1) console.log(`${st} ${ch} ${sc}\n  ` + [rows[0], rows[2], rows[4], rows[9]].join('\n  '))
  }
}
console.log(bad ? `FAIL: ${bad} wrong calls marked as projected winner` : 'PASS: no wrong projected-winner calls')
