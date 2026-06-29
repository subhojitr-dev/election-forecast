// Thin API client. Calls are proxied to the FastAPI backend (see vite.config.js).

export async function getElections() {
  const r = await fetch('/api/elections')
  if (!r.ok) throw new Error('Failed to load elections')
  return r.json()
}

export async function getStates(race, election) {
  const r = await fetch(`/api/states?race=${race}&election=${election}`)
  if (!r.ok) throw new Error('Failed to load states')
  return r.json()
}

export async function getStateDetail(abbr, race, election) {
  const r = await fetch(`/api/state/${abbr}?race=${race}&election=${election}`)
  if (!r.ok) throw new Error(`Failed to load ${abbr}`)
  return r.json()
}

export async function getCountyDetail(abbr, county, race, election) {
  const r = await fetch(`/api/state/${abbr}/county/${encodeURIComponent(county)}?race=${race}&election=${election}`)
  if (!r.ok) throw new Error(`Failed to load ${county}`)
  return r.json()
}

// ---- election-night simulation stepper ----
export async function getScenarios(race) {
  const r = await fetch(`/api/scenarios?race=${race}`)
  return r.json()
}
export async function simReset(race, scenario, election) {
  const r = await fetch(`/api/sim/reset?race=${race}&scenario=${scenario}&election=${election}`, { method: 'POST' })
  return r.json()
}
export async function simNext(race, scenario, election) {
  const r = await fetch(`/api/sim/next?race=${race}&scenario=${scenario}&election=${election}`, { method: 'POST' })
  return r.json()
}
export async function simStatus(race, election) {
  const r = await fetch(`/api/sim/status?race=${race}&election=${election}`)
  return r.json()
}
