# TESTING.md — How to test the dashboard (plain-language guide)

This walks you through everything to test, the exact clicks, and **what you should
see** so you can tell pass from fail. No coding needed — just two servers and a browser.

---

## 0. Start the two servers

Open two terminals in the project folder (`C:\Users\subho\election-forecast`):

```
# Terminal 1 — the data/API server
uvicorn api.main:app --port 8000

# Terminal 2 — the dashboard
cd ui
npm run dev
```

Then open **http://localhost:5173** in your browser.

> Golden rule: if you change anything under `api/` or `ingestor/`, restart Terminal 1
> **and** click **Reset** in the dashboard. Changes under `ui/` apply automatically —
> just refresh the page.

---

## 1. Orientation — what you're looking at

- **Top strip:** the 8 swing states. Click one to make it the focus.
- **Scenario row:** a dropdown (the "what-if" you're watching) + **Reset** + **Next Batch ▶**.
  - **Next Batch ▶** = "let more precincts report" (20% → 40% → … → 100%).
  - **Reset** = start the night over at 0%.
- **President / Senate / GA Special** toggle = which race you're viewing.
- **Panels:** live vote bar, win-probability gauge, convergence line, county table,
  and (top-right) the new **County Insight** box.

**The mental model:** the dashboard compares *tonight's* votes against a *baseline*
(what that area did last election). "Good for the Democrat" = doing **better than the
baseline**, on **higher turnout**, with **uncounted votes leaning their way**.

---

## 2. Test — Convergence line (President)

**What it proves:** the over/under-performance line is continuous, honest, and readable.

**Steps:** Race = **President**. Scenario = **True (real 2020 results)**. Click **Reset**,
then **Next Batch ▶** a few times, watching the bottom **"Convergence vs 2020"** chart.

**What you should see (PASS):**
- The blue line **starts at the far left (0%)** at the dashed **2020 baseline (~50.1%)** —
  no blank gap.
- It is **solid** while the Democrat is **at/above 50%**, and would turn **dashed** (same
  blue) if it dips **below 50%**.
- As you click Next Batch, the line **extends to the right** across a fixed 0→100% frame —
  it does **not** rescale or appear to redraw.
- The y-axis bottom is **30%** (so the 50% line and baseline sit low on the chart).

**To see the dashed style:** switch Race = **President**, click a state the Republican won
(e.g. **NC** or **TX**) — the Democrat is below 50%, so the line shows **dashed**.

---

## 3. Test — Georgia Senate shows Ossoff winning (the runoff fix)

**What it proves:** GA Senate uses the Jan-2021 runoff (Ossoff won), not the Nov general.

**Steps:** Toggle = **Senate**. Select **GA**. Click **Reset**, then **Next Batch ▶** to 100%.

**What you should see (PASS):**
- Candidates are **Jon Ossoff (D)** vs **David A. Perdue (R)**.
- The convergence **baseline sits just above 50%** (~50.8%), and the final result is a
  **Democratic win** (Ossoff) — *not* Perdue.
- Early batches may lean Republican, then it crosses to the Democrat (the runoff pattern).

---

## 4. Test — GA Special seat (Warnock)

**What it proves:** the second Georgia runoff (Warnock vs Loeffler) can be simulated.

**Steps:** Click the **GA Special** toggle (next to President/Senate). Click **Reset**,
then **Next Batch ▶** to 100%.

**What you should see (PASS):**
- The top strip shows **only Georgia** (this race exists only for GA).
- Candidates are **Raphael Warnock (D)** vs **Kelly Loeffler (R)**.
- Progress steps smoothly **20 → 40 → 60 → 80 → 100%** (not jumpy).
- It ends in a **Democratic win** (Warnock, ~51.2%), again after an early R-looking lead.

---

## 5. Test — Ballot buckets + turnout + County Insight (the big feature)

**What it proves:** votes are tracked by type (mail/early/election-day/military); you see
the red-mirage→blue-shift swing; and the County Insight box reads out the benchmark/
turnout/pending story.

**Steps:**
1. Race = **President**. Scenario dropdown = **"TEST · +4% big-county turnout, by ballot type"**.
2. Click **Reset**. Select **GA** in the top strip.
3. Click **Next Batch ▶** once or twice (early in the night), then in the **County table**
   click the **FULTON** row.
4. Look at the **County Insight** box (top-right) and try its **Mail / Election-Day** tabs.
5. Keep clicking **Next Batch ▶** to 100%, watching the top vote bar and the County Insight box.

**What you should see (PASS):**

*Early (after 1–2 batches — the "red mirage"):*
- Georgia's vote bar shows the **Republican ahead** (Dem ~47%).
- County Insight → **Mail tab** says *"No Mail votes counted yet"* (mail reports late).
- The **Fulton note** reads something like: *"48% reporting. Democrat at 77.0% vs the 73.5%
  2020 benchmark (+3.4 pts — above benchmark). Turnout vs 2020 still settling (mail not yet
  counted). ~178,000 votes still to come — and mail (which leans Democratic) is largely
  still uncounted, so the remaining vote likely breaks toward the Democrat."*

*Late (at 100% — the "blue shift"):*
- Georgia's vote bar **flips to the Democrat** (~52%).
- County Insight → **Mail tab** now shows mail votes leaning strongly **Democratic (~69%)**,
  while **Election-Day** leans **Republican (~43%)**.
- The **Fulton note** now reads: *"99% reporting. Democrat at ~75% vs the 73.5% benchmark
  (above). Turnout tracking **+5% vs 2020**."*
- County table has **"Turn v20"** (turnout vs 2020) and **"Pending"** columns filled in.

**The point you're validating:** even though the Republican led early, the box correctly
told you the **uncounted mail would break Democratic** — and that **Fulton was hitting its
2020 benchmark on higher turnout** (the "good sign"). That's the whole upgrade: it reads the
*meaning* of the outstanding vote, not just who's ahead right now.

---

## 6. How to read the key numbers (cheat sheet)

| You see | It means |
|---------|----------|
| **D% Live vs D% 2020** | tonight's Democratic share vs that area's last result. Higher = over-performing. |
| **vs Bench** | live share minus the 2020 benchmark. Green/+ = above benchmark (good for Dem). |
| **Turn v20** | estimated turnout vs 2020 (+ = more people voted). Unreliable until mail is in. |
| **Pending** | estimated votes still to be counted (current count scaled up to 100%). |
| **Convergence line solid vs dashed** | solid = Democrat above 50%; dashed = below 50%. |
| **Mail bucket leaning D, still small** | expect the Democrat to gain as mail is counted. |
| **Win-prob gauge** | chance the Democrat wins, given the projection + how much is reported. |

---

## 7. If something looks wrong

- **Blank panels / "API error":** Terminal 1 (uvicorn on :8000) isn't running.
- **Numbers stuck / old behavior after a backend change:** restart Terminal 1, then click **Reset**.
- **Everything at 100% already:** click **Reset** to start from 0%.
- **GA Special shows only one state:** that's correct — only Georgia has that race.
- **County Insight empty:** click a county row in the table, or step at least one batch.
