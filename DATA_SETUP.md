# DATA_SETUP.md — Data files inventory

Every data file the project uses, with its **full path**, a **brief description of
its contents**, and its **source**. All raw inputs live under `data\raw\`; the
single built artifact lives under `data\db\`.

- **Loaders:** `ingestor/etl_baseline.py` reads the five MIT precinct CSVs;
  `ingestor/etl_ga_runoff_2021.py` reads the Georgia runoff CSV. Both write to
  `data\db\baseline.db`.
- **Target states (8):** GA, PA, AZ, NV, WI, MI, NC, TX.

---

## 1. Baseline input data — precinct-level CSVs (read by the ETL)

| File | Full path | What it contains | Source |
|------|-----------|------------------|--------|
| `PRESIDENT_precinct_general.csv` | `C:\Users\subho\election-forecast\data\raw\PRESIDENT_precinct_general.csv` | **2020 U.S. President**, precinct-level returns (national). The **primary baseline** for all 8 swing states. ~342 MB. | MIT Election Lab · Harvard Dataverse `doi:10.7910/DVN/JXPREB` |
| `2024-PRESIDENT-precinct-general.csv` | `C:\Users\subho\election-forecast\data\raw\2024-PRESIDENT-precinct-general.csv` | **2024 U.S. President**, precinct-level (national). Secondary reference for trend/comparison. ~382 MB. | MIT Election Lab · Harvard Dataverse `doi:10.7910/DVN/XDJYKC` |
| `2020-SENATE-precinct-general.csv` | `C:\Users\subho\election-forecast\data\raw\2020-SENATE-precinct-general.csv` | **2020 U.S. Senate general**, precinct-level (34 states). Supplies the 2020 Senate baseline for **NC** (current), plus historical GA/AZ/MI/TX. GA's Nov-2020 rows are superseded by the 2021 runoff (see row below). ~157 MB. | MIT Election Lab · Harvard Dataverse `doi:10.7910/DVN/ER9XTV` |
| `2024-SENATE-precinct-general.csv` | `C:\Users\subho\election-forecast\data\raw\2024-SENATE-precinct-general.csv` | **2024 U.S. Senate**, precinct-level (national). Current Senate baseline for **AZ, MI, PA, NV, WI, TX**; fills PA/NV/WI (no 2020 Senate race). ~159 MB. | MIT Election Lab · Harvard Dataverse `doi:10.7910/DVN/ZCM3BN` |
| `2018-SENATE-precinct-general.csv` | `C:\Users\subho\election-forecast\data\raw\2018-SENATE-precinct-general.csv` | **2018 U.S. Senate**, precinct-level (national). Historical baseline, incl. TX Cruz–O'Rourke; coverage for AZ/MI/TX/NV/PA/WI. ~126 MB. | MIT Election Lab · Harvard Dataverse `doi:10.7910/DVN/DGNAFS` |
| `20210105__ga__runoff.csv` | `C:\Users\subho\election-forecast\data\raw\ga_runoff_2021\20210105__ga__runoff.csv` | **Georgia Jan 5, 2021 RUNOFF**, precinct-level. Holds **both** U.S. Senate seats — Ossoff–Perdue (regular) and Warnock–Loeffler (special) — plus Public Service Commissioner. Aggregated to county → GA Senate baselines `senate` + `senate_special` (election_year 2021). 155/159 counties (Issue #7). ~1.2 MB. | OpenElections · `github.com/openelections/openelections-data-ga` (`2021/20210105__ga__runoff.csv`) |
| `gov2022/AZ-cleaned.tab`, `gov2022/ga22_cleaned.tab`, `gov2022/TX-cleaned.tab` | `C:\Users\subho\election-forecast\data\raw\gov2022\` | **2022 state offices, precinct-level, per-state** — filtered to `office=='GOVERNOR'` by `etl_governor_2022.py`. GA/AZ/TX's last Governor election (Kemp/Hobbs/Abbott's terms all end 2026). ~100-125MB each, gitignored (`*.tab`). **Not manually downloaded** — `etl_governor_2022.py` auto-downloads + deletes each file after ingesting (self-seeding, see that script's docstring; requires a browser User-Agent header, Dataverse 403s a bare one — confirmed 2026-08-08). | MIT Election Lab · Harvard Dataverse, dataset `doi:10.7910/DVN/UYQIEP` ("Precinct-Level Returns 2022 by Individual State") · file ids 10855167 (AZ) / 10855164 (GA) / 10855154 (TX) |
| `me_2020_senate_county_results.json` | `C:\Users\subho\election-forecast\ingestor\me_2020_senate_county_results.json` | **Maine 2020 Senate (Collins–Gideon), county level** — a small (~9KB, 68-row) fixture **committed to git** (not gitignored — deliberately, unlike everything else in this table). Verified against certified results (Collins 51.00% vs certified 50.98%). NOT auto-downloaded like the Governor files above: the source dataset requires a Dataverse "Guestbook" response (a one-time human form) before ANY download succeeds — confirmed 2026-08-08, no way around it with headers/UA tricks. Since Maine's actual needed slice is tiny and historically fixed, baked it in directly instead of fighting that gate at runtime. | Extracted from MEDSL's national 2020 Senate file (`doi:10.7910/DVN/ER9XTV`, file id 6100391 — same dataset as `2020-SENATE-precinct-general.csv` above) |

---

## 2. Codebook & dataset READMEs (reference, not loaded)

| File | Full path | What it contains | Source |
|------|-----------|------------------|--------|
| `2020-precincts-codebook.md` | `C:\Users\subho\election-forecast\data\raw\docs\2020-precincts-codebook.md` | Column-by-column definitions for the MIT precinct CSVs (e.g. `state_po`, `special`, `stage`, `mode`, `votes`). | MIT Election Lab |
| `README-president.md` | `C:\Users\subho\election-forecast\data\raw\docs\README-president.md` | MIT dataset README for the President precinct files (notes, caveats, processing). | MIT Election Lab |
| `README-senate.md` | `C:\Users\subho\election-forecast\data\raw\docs\README-senate.md` | MIT dataset README for the Senate precinct files. | MIT Election Lab |

---

## 3. Live-feed format samples (Clarity XML, for parser tests)

| File | Full path | What it contains | Source |
|------|-----------|------------------|--------|
| `county.xml` | `C:\Users\subho\election-forecast\data\raw\clarity_samples\county.xml` | A **real Clarity ENR county-level XML** sample. Validates the live parser (`ingestor/clarity_poller.py`) reads the genuine format. | `openelections/clarify` test fixtures |
| `precinct.xml` | `C:\Users\subho\election-forecast\data\raw\clarity_samples\precinct.xml` | A **real Clarity ENR precinct-level XML** sample, same purpose. | `openelections/clarify` test fixtures |

---

## 4. Built database (generated output — not a raw input)

| File | Full path | What it contains | Source |
|------|-----------|------------------|--------|
| `baseline.db` | `C:\Users\subho\election-forecast\data\db\baseline.db` | The project's **SQLite database**, built from the files above. Tables: **`precincts`**, **`results_historical`**, **`county_rollup`** (the certified baselines), and **`results_live`** + **`live_snapshots`** (current live/simulated results + per-poll time series). ~192 MB. | Generated by `ingestor/etl_baseline.py` + `ingestor/etl_ga_runoff_2021.py` |

---

## Rebuild from scratch

```bash
python ingestor/etl_baseline.py          # builds baseline.db from the 5 MIT CSVs
python ingestor/etl_ga_runoff_2021.py    # adds the GA 2021 runoff (senate + senate_special)
python integration_test.py               # verifies all 8 states × 2 races reproduce reality
```

> Dataverse page pattern: `https://dataverse.harvard.edu/dataset.xhtml?persistentId=<doi>`
