// Panel 5 — Convergence Tracker.
// Live Dem two-party %: SOLID blue while >= 50% (Dem ahead), DASHED blue (same
// colour) while < 50% (Dem behind). Dashed grey flat = 2020 baseline.
// X is a fixed 0–100% frame so the line only ever EXTENDS rightward as fresh
// results arrive — it reads as a continuation, not a redraw. Y floors at 30%.
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'

export default function ConvergenceChart({ detail }) {
  const baseline = detail?.baseline_dem_share != null
    ? +(detail.baseline_dem_share * 100).toFixed(2) : null

  // 1) Live Dem two-party % per snapshot. At 0% reporting there are no votes
  //    (share is null), so anchor that point at the 2020 baseline.
  const raw = (detail?.series || []).map((p) => ({
    pct: p.pct_reporting,
    live: p.dem_share_2pty != null
      ? p.dem_share_2pty * 100
      : (p.pct_reporting === 0 ? baseline : null),
    proj: p.projected_dem_share != null ? p.projected_dem_share * 100 : null,
  }))

  // 2) Insert a synthetic point exactly where the live line crosses 50% so the
  //    solid (>=50) / dashed (<50) split switches precisely on the 50% line.
  const live = raw.filter((p) => p.live != null)
  const dense = []
  for (let i = 0; i < live.length; i++) {
    const cur = live[i]
    if (i > 0) {
      const prev = live[i - 1]
      if ((prev.live - 50) * (cur.live - 50) < 0) {
        const t = (50 - prev.live) / (cur.live - prev.live)
        dense.push({ pct: prev.pct + t * (cur.pct - prev.pct), live: 50, proj: null })
      }
    }
    dense.push(cur)
  }

  // 3) Two same-colour series: solid above 50%, dashed below. The 50% crossing
  //    point belongs to BOTH so the segments meet seamlessly at the boundary.
  const series = dense.map((p) => ({
    pct: +p.pct.toFixed(1),
    liveAbove: p.live >= 50 ? +p.live.toFixed(2) : null,
    liveBelow: p.live <= 50 ? +p.live.toFixed(2) : null,
    proj: p.proj != null ? +p.proj.toFixed(2) : null,
  }))

  // Y floor at 30% — no realistic candidate dips below; drop lower only if one does.
  const lows = series.flatMap((p) => [p.liveAbove, p.liveBelow]).filter((v) => v != null)
  const yFloor = lows.length ? Math.min(30, Math.floor(Math.min(...lows))) : 30

  return (
    <div className="panel">
      <h2>Convergence vs 2020 — Democratic two-party %</h2>
      {series.length === 0 ? (
        <div className="empty">No live results yet. The line will track Dem share as precincts report.</div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
            <CartesianGrid stroke="#2a3038" strokeDasharray="3 3" />
            <XAxis dataKey="pct" type="number" domain={[0, 100]} ticks={[0, 20, 40, 60, 80, 100]}
                   stroke="#8b949e" tick={{ fontSize: 11 }}
                   label={{ value: '% precincts reporting', position: 'insideBottom', offset: -2, fill: '#8b949e', fontSize: 11 }} />
            <YAxis stroke="#8b949e" tick={{ fontSize: 11 }} domain={[yFloor, 'auto']}
                   tickFormatter={(v) => v + '%'} width={48} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #2a3038', color: '#e6edf3' }}
                     formatter={(v) => v + '%'} labelFormatter={(l) => l + '% reporting'} />
            {baseline != null && (
              <ReferenceLine y={baseline} stroke="#8b949e" strokeDasharray="6 4"
                             label={{ value: `2020 baseline ${baseline}%`, fill: '#8b949e', fontSize: 10, position: 'insideTopRight' }} />
            )}
            <ReferenceLine y={50} stroke="#555" />
            {/* Solid = Dem at/above 50%; dashed = same blue line below 50%. */}
            <Line type="monotone" dataKey="liveAbove" name="Live Dem %" stroke="#3b82f6"
                  strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="liveBelow" name="Live Dem % (below 50%)" stroke="#3b82f6"
                  strokeWidth={2.5} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="proj" name="Projected" stroke="#f0c040"
                  strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
