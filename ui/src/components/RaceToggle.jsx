// Panel 2 — Race Toggle. Buttons are driven by the active election's race list
// (from the ballot manifest), so on a real election night only the contests
// actually happening appear (e.g. Nov-2026 = Senate only, no President).
const LABEL = { president: 'President', senate: 'Senate', senate_special: 'GA Special (Warnock)' }
const TITLE = { senate_special: 'Georgia-only: the Jan-2021 Warnock vs Loeffler special-seat runoff' }
// Races scoped to a single state — greyed out and unclickable unless that
// state is the one currently selected, so the toggle doesn't imply this
// option applies to whichever state you're looking at (it doesn't).
const ONLY_STATE = { senate_special: 'GA' }

export default function RaceToggle({ races, race, onChange, selected }) {
  if (!races || races.length === 0) return null
  return (
    <div className="toggle">
      {races.map((r) => {
        const id = typeof r === 'string' ? r : r.id
        const label = (typeof r === 'object' && r.label) || LABEL[id] || id
        const onlyState = ONLY_STATE[id]
        const disabled = onlyState && selected !== onlyState
        const title = disabled
          ? `${TITLE[id] || ''} — select ${onlyState} to view this race`.trim()
          : (TITLE[id] || '')
        return (
          <button key={id} className={race === id ? 'on' : ''} title={title}
                  disabled={disabled}
                  onClick={() => onChange(id)}>
            {label}
          </button>
        )
      })}
    </div>
  )
}
