// Small formatting helpers shared across panels.

export const num = (x) => (x == null ? '—' : Math.round(x).toLocaleString())
export const pct1 = (x) => (x == null ? '—' : (x * 100).toFixed(1) + '%')

// shift is a two-party share fraction (e.g. -0.03 = R+3.0). Positive = toward D.
export const shiftLabel = (s) => {
  if (s == null) return '—'
  const pts = (s * 100).toFixed(1)
  return s >= 0 ? `D+${pts}` : `R+${Math.abs(pts)}`
}

export const leansDem = (prob) => (prob ?? 0.5) >= 0.5
