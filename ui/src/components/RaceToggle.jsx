// Panel 2 — Race Toggle. Buttons are driven by the active election's race list
// (from the ballot manifest), so on a real election night only the contests
// actually happening appear (e.g. Nov-2026 = Senate only, no President).
const LABEL = { president: 'President', senate: 'Senate', senate_special: 'GA Special' }
const TITLE = { senate_special: 'Georgia-only: the Jan-2021 Warnock vs Loeffler special-seat runoff' }

export default function RaceToggle({ races, race, onChange }) {
  if (!races || races.length === 0) return null
  return (
    <div className="toggle">
      {races.map((r) => {
        const id = typeof r === 'string' ? r : r.id
        const label = (typeof r === 'object' && r.label) || LABEL[id] || id
        return (
          <button key={id} className={race === id ? 'on' : ''} title={TITLE[id] || ''}
                  onClick={() => onChange(id)}>
            {label}
          </button>
        )
      })}
    </div>
  )
}
