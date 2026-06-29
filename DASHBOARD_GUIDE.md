# Dashboard Guide — Election Forecast

A plain-English walkthrough of what the dashboard shows, how to read it, and how
to simulate an election night. Pairs best with the live dashboard open in front
of you (see "How to start it" below). Screenshots from the build session
illustrate each section.

---

## 1. The big idea (read this first)

On election night, raw numbers ("Candidate X leads by 12,000") don't tell you
much on their own — you need a **reference point**. This dashboard's reference
point is **the last election's certified result** (2020 for President, the most
recent Senate race per state).

So every number is really answering one question:

> **Is this area doing better or worse than last time — and what does that mean
> for who wins?**

That comparison ("the shift") is the heart of everything you see.

Two terms used everywhere:
- **Two-party share** — we measure the Democrat's share of just the D+R vote
  (ignoring third parties), so the signal isn't muddied. "50.1%" means 50.1% of
  the two-party vote.
- **Shift** — how much the Democrat is over/under-performing vs the baseline,
  in percentage points. Shown as **D+1.9** (Democrats doing better) or **R+2.3**
  (Republicans doing better). Blue = D gain, red = R gain.

---

## 2. How to start it

Open **two PowerShell windows** (both stay open while you use the dashboard):

```powershell
# Window 1 — the data API. Run from the PROJECT ROOT:
cd C:\Users\subho\election-forecast
python -m uvicorn api.main:app --port 8000
#   (this is the verified command; "uvicorn api.main:app --port 8000" also works
#    IF the uvicorn command is on your PATH)

# Window 2 — the dashboard. Run from the ui FOLDER:
cd C:\Users\subho\election-forecast\ui
npm run dev
```

Notes:
- Run the API from the **project root** (not inside `api\`) — `api.main` is
  resolved from there.
- PowerShell doesn't support `&&`; use separate lines (or `cd ui ; npm run dev`).
- BOTH must be running at once. If the API window is closed, the dashboard shows
  "API error: … is the backend running on :8000?" — just restart Window 1.

The dashboard is at:

> ### → http://localhost:5173

That is the **only URL you need to open**. Behind the scenes it talks to the data
API on **port 8000** for you — you don't visit that directly (though
`http://localhost:8000/docs` lets you peek at the raw API if curious). Both
programs must be *running*, but you only *open* 5173.

**Why two ports?** They're two separate programs: the **data engine** (FastAPI /
Python, port 8000) does the analysis and serves numbers; the **dashboard UI**
(Vite / React, port 5173) is what you look at. Think kitchen (8000) vs dining
room (5173) — you sit in the dining room, and it relays orders to the kitchen.
(In Phase 7 / deployment we put both behind a single public URL, so this
two-port split is only a local-development detail.)

---

## 3. The screen layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  🗳️ Election Forecast                              ● auto-refresh 5s   │
├──────────────────────────────────────────────────────────────────────┤
│  [GA] [PA] [AZ] [NV] [WI] [MI] [NC] [TX]      ← Panel 1: state strip   │
├──────────────────────────────────────────────────────────────────────┤
│  Scenario [▼]  [Reset] [Next Batch ▶]            45% reporting  ▓▓▓░░   │  ← Simulator
├───────────────────────────────────────────┬──────────────────────────┤
│  [President | Senate]  [search county…]    │   WATCH LIST   (Panel 9)  │
│                                            │   counties with the most  │
│  ┌─ LIVE VOTE (Panel 4) ─┐ ┌ WIN PROB ─┐  │   votes still out         │
│  │ Biden 50.1% Trump 49.9│ │  (gauge)  │  │                           │
│  └───────────────────────┘ └ Panel 6 ──┘  │   EV TRACKER   (Panel 10) │
│  CONVERGENCE CHART  (Panel 5)              │   all states' EV + lean   │
│  COUNTY SHIFT BARS  (Panel 8)              │                           │
│  COUNTY TABLE       (Panel 7)              │                           │
└────────────────────────────────────────────┴─────────────────────────┘
```

---

## 4. Panel-by-panel — what to see & what to look for

### Panel 1 — Swing-State Strip (top row)
Eight clickable cards. Each shows: **state + electoral votes**, the **lean**
(e.g. "Tilt D 60.1%"), **% reporting**, and **shift vs the baseline**.
- **Blue top-border = currently Democratic, red = Republican.**
- The **gold-outlined** card is the one you're viewing in detail below.
- **What to look for:** which states are close ("Toss-Up"), and whether the
  shift is blue or red. **Click any card** to drill into it.

### Panel 2 — Race Toggle
`President | Senate`. Switches every panel between the two races.
- **Note:** Senate compares against each state's *most recent* Senate race
  (GA & NC = 2020; the rest = 2024), since not every state had a 2020 Senate race.

### Panel 3 — County Search
Type a county name (e.g. `FULTON`) to instantly filter the county table below.

### Panel 4 — Live Vote Bar
The two candidates, their live vote totals, percentages, the blue/red split bar,
and **who leads by how much**.
- **What to look for:** the margin, and remember it can be misleading early
  (see "red mirage" in §7).

### Panel 5 — Convergence Chart
A line of the **live Democratic %** as precincts report, against a **dashed flat
line = the 2020 baseline**.
- **Solid line ABOVE dashed →** Democrat doing better than 2020.
- **Solid line BELOW dashed →** Democrat doing worse.
- The gap between them *is* the story of the night.

### Panel 6 — Win Probability Gauge
A needle between **DEM (blue, left)** and **REP (red, right)**.
- Below it: the **lean label** ("Tilt D", "Safe R", …) and the **confidence
  tier** ("Very Early", "Near Final", …). See the legend in §6.
- **What to look for:** the needle moves toward the leader, and the probability
  firms up (toward 0% or 100%) as more votes come in.

### Panel 7 — County Breakdown Table
One row per county: **% reporting, D% live, D% 2020, Shift, Votes In**. Click a
column header to sort.
- **Shift column is color-coded** (blue = D gain, red = R shift).
- **What to look for:** big counties (high "Votes In") and their shift — they
  move the statewide result the most.

### Panel 8 — County Shift Bars
A bar per county (the biggest movers): **right/blue = D shift, left/red = R
shift** vs the baseline.
- **What to look for:** are the bars mostly blue or mostly red? That's the
  direction of the whole state at a glance.

### Panel 9 — Watch List (right sidebar)
Auto-generated: counties with the **most votes still outstanding** (and close
past margins) — the highest-impact places still to report.
- **What to look for:** if the leader is ahead but the watch list is full of
  blue-leaning counties yet to report, the lead may shrink.

### Panel 10 — EV Tracker (right sidebar)
Mini scoreboard of all 8 states: electoral votes + lean, and a running
**D vs R electoral-vote tally**. Click a state to jump to it.

---

## 5. The win-probability legend

**Lean labels** (from the Dem win probability):
`Safe D` ≥ 97% · `Likely D` ≥ 85% · `Lean D` ≥ 65% · `Tilt D` > 55% ·
**`Toss-Up`** 45–55% · `Tilt R` · `Lean R` · `Likely R` · `Safe R` (mirror).

**Confidence tiers** (from % reporting — how much to trust it yet):
- **Very Early — Directional Only** (<15% in)
- **Early — Lean Forming** (15–40%)
- **Developing — Probable** (40–70%)
- **Strong Signal** (70–90%)
- **Near Final** (>90%)

> Early on, the forecast deliberately stays close to the 2020 baseline and only
> trusts the live swing more as more precincts report. So a small early lead won't
> swing the probability much — by design.

---

## 6. How to simulate an election night (the fun part)

There's no live 2026 data yet, so the dashboard **replays** a real past election,
revealing precincts in batches — like watching results trickle in.

The **simulator bar** (just under the state strip):

1. **Scenario** dropdown — pick what to replay (see §7).
2. **Reset** — clears to 0% and loads the chosen scenario.
3. **Next Batch ▶** — reveals the next ~20% of precincts. Click it five times to
   go 20 → 40 → 60 → 80 → 100%.
4. **Progress bar** — shows overall % reporting.

> On the **real election day**, this button is replaced automatically by the live
> data poller (it pulls fresh results every 60 seconds). Same dashboard, same
> math — the only difference is where the data comes from.

**Try this:** Reset → click Next Batch slowly, and watch the gauge, the
convergence line, and the watch list change with each batch.

---

## 7. The scenarios

**President:**
- **True (real 2020 results)** — replays what actually happened. Shift reads ~0
  everywhere (it *is* 2020 vs 2020). Biden wins GA/PA/AZ/NV/WI/MI; Trump wins
  NC/TX.
- **Ossoff vs Vance · D+5** — *hypothetical for fun*: the 2020 vote map but with
  a 5-point Democratic swing, relabeled as Jon Ossoff vs JD Vance.
- **AOC vs Vance · D+5** — same favorable-D environment, relabeled AOC vs Vance.

**Senate:**
- **True (most-recent real results)**
- **Democrats D+5 (real candidates)** — a favorable-D environment over the real
  candidates.

> ⚠️ The "D+5" scenarios are **made-up "what-ifs"**, not predictions — they apply
> an artificial uniform swing to a real past vote map, just to see how a favorable
> Democratic environment would look across these states.

---

## 8. What to look for — a guided tour

1. **Pick "True (real 2020)", Reset, step to ~20%.** Notice the lead can look
   different from the final — early-reporting areas aren't representative.
2. **Watch the Convergence chart** as you step: the live line settling relative
   to the dashed 2020 line tells you if a state is out- or under-performing 2020.
3. **Watch the Win Probability gauge** firm up: Toss-Up → Lean → Safe as the
   confidence tier climbs from "Very Early" to "Near Final".
4. **Red mirage / blue shift:** in real life, Republican-leaning (election-day)
   precincts often report first and Democratic (mail) ones later — so an early
   red lead can fade. The D+5 hypotheticals are a good way to see a lead move.
5. **Use the Watch List** to judge whether a current lead is safe: lots of
   outstanding votes in the trailing candidate's strong counties = not safe yet.
6. **Check the EV Tracker** for the big picture across all 8 states at once.

---

## 9. Important caveats (so nothing is misleading)

- **This is a replay, not live data.** It's June 2026; the election is Nov 3,
  2026. We're testing the system against past elections until then.
- **The D+5 scenarios are synthetic** — relabeled candidates + an artificial
  swing over a real vote map. Not forecasts.
- **Senate uses different baseline years per state** (PA/NV/WI had no 2020 Senate
  race), so a Senate comparison is "vs that state's most recent Senate race".
- **Precinct matching for the real night** still needs a "crosswalk" (matching
  2026 precincts to old ones) — see `Issues.md`. Until then, anything that can't
  be matched falls back to county-level comparison.

---

## 10. Quick reference

| You see | It means |
|---|---|
| **Blue** | Democratic |
| **Red** | Republican |
| **D+2.3 / R+1.9** | shift vs baseline (D or R doing 2.3 / 1.9 pts better) |
| **% reporting** | how much of the vote is counted so far |
| **Tilt / Lean / Likely / Safe** | how confident the winner call is |
| **Toss-Up** | too close to call (45–55% each) |
| **Watch List** | counties with the most votes still to come |
| **Convergence chart** | live Dem % vs the flat 2020 baseline |

---

*Build status & open items live in `CONTEXT.md` (current state), `PROGRESS.md`
(history), and `Issues.md` (known issues + the path to election night).*
