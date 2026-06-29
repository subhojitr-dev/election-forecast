import { useEffect, useState, useCallback } from 'react'
import { getElections, getStates, getStateDetail, getScenarios, simReset, simNext, simStatus } from './api'
import SwingStateStrip from './components/SwingStateStrip'
import RaceToggle from './components/RaceToggle'
import SimControls from './components/SimControls'
import LiveVoteBar from './components/LiveVoteBar'
import WinProbGauge from './components/WinProbGauge'
import ConvergenceChart from './components/ConvergenceChart'
import CountyShiftBars from './components/CountyShiftBars'
import CountyTable from './components/CountyTable'
import WatchList from './components/WatchList'
import EVTracker from './components/EVTracker'
import CountyInsight from './components/CountyInsight'

const POLL_MS = 10000

export default function App() {
  const [electionsList, setElectionsList] = useState([])
  const [election, setElection] = useState('demo')
  const [race, setRace] = useState('president')
  const [statesData, setStatesData] = useState(null)
  const [selected, setSelected] = useState('GA')
  const [selectedCounty, setSelectedCounty] = useState(null)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  // simulation state
  const [scenarios, setScenarios] = useState([])
  const [scenario, setScenario] = useState('true')
  const [sim, setSim] = useState(null)
  const [busy, setBusy] = useState(false)

  // races available for the active election (from the ballot manifest)
  const races = electionsList.find((e) => e.id === election)?.races || []

  // load the election manifest once
  useEffect(() => {
    (async () => {
      try {
        const data = await getElections()
        setElectionsList(data.elections)
        const def = data.default || 'demo'
        setElection(def)
        const defRaces = data.elections.find((e) => e.id === def)?.races || []
        if (defRaces.length) setRace(defRaces[0].id)
      } catch { /* ignore */ }
    })()
  }, [])

  const refresh = useCallback(async () => {
    if (!race) return
    try {
      const [sd, det] = await Promise.all([
        getStates(race, election),
        getStateDetail(selected, race, election),
      ])
      setStatesData(sd)
      setDetail(det)
      setError(null)
    } catch (e) {
      setError(e.message || 'Request failed')
    }
  }, [race, selected, election])

  // load scenarios + current sim status when the race or election changes
  useEffect(() => {
    if (!race) return
    (async () => {
      try {
        const sc = await getScenarios(race)
        setScenarios(sc.scenarios)
        setScenario((cur) => (sc.scenarios.some((s) => s.id === cur) ? cur : 'true'))
        setSim(await simStatus(race, election))
      } catch { /* ignore */ }
    })()
  }, [race, election])

  // periodic refresh (live feel; on real election night this is the poller)
  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  const onNext = async () => {
    setBusy(true)
    try { setSim(await simNext(race, scenario, election)); await refresh() } finally { setBusy(false) }
  }
  const onReset = async () => {
    setBusy(true)
    try { setSim(await simReset(race, scenario, election)); await refresh() } finally { setBusy(false) }
  }
  const onScenario = async (id) => {
    setScenario(id)
    setBusy(true)
    try { setSim(await simReset(race, id, election)); await refresh() } finally { setBusy(false) }
  }

  // GA special seat is GA-only — force the selected state to GA when entering it.
  const onRaceChange = (r) => {
    if (r === 'senate_special') setSelected('GA')
    setSelectedCounty(null)
    setRace(r)
  }
  const onSelectState = (s) => { setSelected(s); setSelectedCounty(null) }

  // switching elections re-points the race toggle to that election's races
  const onElectionChange = (eid) => {
    const eRaces = electionsList.find((e) => e.id === eid)?.races || []
    setElection(eid)
    setSelected('GA')          // GA is on the ballot in every configured election
    setSelectedCounty(null)
    if (eRaces.length) setRace(eRaces[0].id)
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>🗳️ Election Forecast</h1>
        <span className="sub">Live results vs baseline · precinct-level</span>
        <span className="live"><span className="dot">●</span> auto-refresh {POLL_MS / 1000}s</span>
      </header>

      {error && <div className="err">API error: {error} — is the backend running on :8000?</div>}

      <SwingStateStrip states={statesData?.states} selected={selected} onSelect={onSelectState} />

      <SimControls scenarios={scenarios} scenario={scenario} onScenario={onScenario}
                   sim={sim} onNext={onNext} onReset={onReset} busy={busy} />

      <div className="main">
        <div className="left">
          <div className="toolbar">
            <div className="election-pick">
              <label>Election</label>
              <select value={election} onChange={(e) => onElectionChange(e.target.value)}>
                {electionsList.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
              </select>
            </div>
            <RaceToggle races={races} race={race} onChange={onRaceChange} />
            <div className="search">
              <input placeholder="Search a county…" value={search}
                     onChange={(e) => setSearch(e.target.value)} />
            </div>
            {detail && (
              <span className="muted" style={{ fontSize: 13 }}>
                {detail.name} · {Math.round(detail.pct_reporting)}% reporting · {detail.confidence_tier}
              </span>
            )}
          </div>

          <div className="row2">
            <LiveVoteBar detail={detail} />
            <WinProbGauge detail={detail} />
          </div>

          <ConvergenceChart detail={detail} />
          <CountyShiftBars detail={detail} />
          <CountyTable detail={detail} search={search}
                       onSelectCounty={setSelectedCounty} selectedCounty={selectedCounty} />
        </div>

        <aside className="sidebar">
          <CountyInsight detail={detail} race={race} election={election} selectedCounty={selectedCounty} />
          <WatchList detail={detail} />
          <EVTracker data={statesData} selected={selected} onSelect={onSelectState} />
        </aside>
      </div>
    </div>
  )
}
