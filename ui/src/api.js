// Thin API client. Calls are proxied to the FastAPI backend.
// Dev: leave VITE_API_BASE unset -> relative URLs, proxied by Vite (vite.config.js).
// Prod: set VITE_API_BASE=https://<backend-host> on Vercel (see DEPLOY.md).
const API = import.meta.env.VITE_API_BASE || ''

export async function getElections() {
  const r = await fetch(`${API}/api/elections`)
  if (!r.ok) throw new Error('Failed to load elections')
  return r.json()
}

export async function getStates(race, election) {
  const r = await fetch(`${API}/api/states?race=${race}&election=${election}`)
  if (!r.ok) throw new Error('Failed to load states')
  return r.json()
}

export async function getStateDetail(abbr, race, election) {
  const r = await fetch(`${API}/api/state/${abbr}?race=${race}&election=${election}`)
  if (!r.ok) throw new Error(`Failed to load ${abbr}`)
  return r.json()
}

export async function getCountyDetail(abbr, county, race, election) {
  const r = await fetch(`${API}/api/state/${abbr}/county/${encodeURIComponent(county)}?race=${race}&election=${election}`)
  if (!r.ok) throw new Error(`Failed to load ${county}`)
  return r.json()
}

// ---- election-night simulation stepper ----
export async function getScenarios(race) {
  const r = await fetch(`${API}/api/scenarios?race=${race}`)
  return r.json()
}
export async function simReset(race, scenario, election) {
  const r = await fetch(`${API}/api/sim/reset?race=${race}&scenario=${scenario}&election=${election}`, { method: 'POST' })
  return r.json()
}
export async function simNext(race, scenario, election) {
  const r = await fetch(`${API}/api/sim/next?race=${race}&scenario=${scenario}&election=${election}`, { method: 'POST' })
  return r.json()
}
export async function simStatus(race, election) {
  const r = await fetch(`${API}/api/sim/status?race=${race}&election=${election}`)
  return r.json()
}
