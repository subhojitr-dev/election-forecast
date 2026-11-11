# Districts tab — GA, NC & SC legislature

App: https://election-forecast-silk.vercel.app/#/districts/GA  (and `/NC`)

| View | URL | What it shows |
|---|---|---|
| 2026 results | `#/districts/GA` | Every State House/Senate seat: result, US Senate margin on the same ballots, **edge** (candidate vs top of ticket), change since 2024 |
| One district | `#/districts/GA/house/108` | Result, edge, vs 2024, by vote method / county / precinct |
| 2028 targets | `#/districts/GA/targets` | Closest R holds, R seats Ossoff/Cooper won, R seats with no Democrat, D seats to defend |
| Election night | `#/districts/GA/live` (`/live/senate`, `/live/house/108`) | Projected margin + win chance per district; **Practice** replays 2026; **Live** reads the API |

## Data (static, served by Vercel — no backend)

```bash
py ingestor/district_results.py ALL      # GA ~4 min (API calls, cached in data/raw/districts), NC seconds
```
Writes `ui/public/districts/{ST}.json`, `{ST}/{house|senate}-N.json`, `{ST}/baseline-{house|senate}.json`.
**Re-run NC after NCSBE posts the 2026 precinct-sorted file (late Nov)** — it is used
automatically and the "estimated" note on multi-district counties goes away.

Validated: GA Ossoff 2,468,990 / Collins 1,713,658 and NC Cooper 2,480,707 / Whatley 1,648,593
exact; NC all 170 districts exact; GA 14 districts off by 1–4 votes.

## Election-night model (`ui/src/districts/model.js`)

1. Each fully counted precinct (× vote method in NC) is compared with the same unit in 2026 → district swing.
2. Blended with the chamber-wide swing until the district has ~2,500 votes of its own evidence.
3. Uncounted units = counted so far + remaining expected votes at (2026 share + swing).
4. Win chance = normal CDF; uncertainty 10 pts with nothing counted, shrinking with the counted share.
   "Projected" only at >99.5% with ≥50% counted.

Baseline = the 2026 race for that seat, or the 2026 US Senate vote where the seat was uncontested.

Checks (run from `ui/`):
```bash
node scripts/calibrate-districts.mjs                 # replays 2026 x 4 scenarios x 3 seeds: no wrong "projected" calls
node scripts/check-live-feed.mjs <live_GA.json> GA   # a feed snapshot of a finished election must reproduce it exactly
```

## Going live (next GA/NC general or special)

1. Find the election id: GA → https://results.sos.ga.gov/results/public/Georgia (the link slug,
   e.g. `11032026GeneralAndSpecialElection`); NC → the ENRS date folder (`YYYY-MM-DD`).
2. Render → Environment: `DISTRICT_LIVE_GA_EID=…` and/or `DISTRICT_LIVE_NC_DATE=…`, plus
   `ENABLE_POLLER=1`, `POLLER_MODE=prod`. GA polls every 3 min (~2 min per poll, ~700 calls); NC every 60 s.
3. Smoke test any time: `py ingestor/district_live_feed.py GA <eid>` then open `/api/districts/live/GA`.
4. **New maps?** GA/NC used the same legislative maps in 2024 and 2026. If either redraws, rebuild
   the baseline from the latest election on the new map (precincts not in the baseline are counted,
   not projected).

Known caveat: GA precinct `reportingStatus` codes differ by county (certified 2026: Fulton/Cobb = 3,
Fayette = 4). A precinct counts as done if it is 3 OR the county reports the contest fully in, so
Fayette-style counties look "partly in" until finished — cautious, never early. Watch this at the
next live GA special election (GA holds several a year) and adjust `GA_DONE_STATUS` if needed.

## South Carolina

- **2024** (all 124 House + 46 Senate seats): MIT Election Lab official precinct file,
  downloaded automatically from github.com/MEDSL/2024-elections-official (`sc24.zip`).
  Validated: House 88 R–36 D, Senate 34 R–12 D; President within 0.03% of certified.
  SC has fusion voting — candidates are merged across party lines by name.
- **2026** (124 House seats + SD-15 special): SC Election Commission ENR, election **127300**
  (county ids in its `electionsettings.json` → `participatingcounties`). Per county:
  `/SC/{County}/{eid}/{ver}/json/en/summary.json` (candidates) + `/json/details.json`
  (precinct votes). **Not loaded yet:** the site's CDN refuses scripted requests and
  rate-limits bulk reads, so it must not be scraped around. Save the export as
  `data/raw/districts/sc/sc_2026_enr.json` (format in `load_sc`) and re-run
  `py ingestor/district_results.py SC` — 2026 then becomes the House baseline automatically.
- **Senate** baseline stays 2024 (next regular SC Senate election is 2028).
- **Live:** `DISTRICT_LIVE_SC_EID` → `district_live_feed.fetch_sc`. ⚠️ Blocked to scripts as of
  Nov 2026 (open in July 2026) — re-test before a live night; if still blocked, SC is practice-only.
