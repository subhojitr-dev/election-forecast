// Panel 8 — County Shift bar chart. One bar per county, left = R shift, right = D shift.
import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

export default function CountyShiftBars({ detail }) {
  const reporting = (detail?.counties || []).filter((c) => c.shift != null && c.pct_reporting > 0)
  // show the 18 counties with the largest absolute shift (most movement)
  const data = reporting
    .map((c) => ({ county: c.county, shift: +(c.shift * 100).toFixed(2) }))
    .sort((a, b) => Math.abs(b.shift) - Math.abs(a.shift))
    .slice(0, 18)
    .sort((a, b) => a.shift - b.shift)

  return (
    <div className="panel">
      <h2>County Shift vs 2020 (largest movers)</h2>
      {data.length === 0 ? (
        <div className="empty">No counties reporting yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(160, data.length * 18 + 40)}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <XAxis type="number" stroke="#8b949e" tick={{ fontSize: 10 }}
                   tickFormatter={(v) => (v > 0 ? `D+${v}` : `R+${-v}`)} />
            <YAxis type="category" dataKey="county" stroke="#8b949e" width={90} tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #2a3038', color: '#e6edf3' }}
                     formatter={(v) => (v > 0 ? `D+${v}` : `R+${-v}`)} />
            <ReferenceLine x={0} stroke="#555" />
            <Bar dataKey="shift">
              {data.map((d, i) => <Cell key={i} fill={d.shift >= 0 ? '#3b82f6' : '#ef4444'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
