import { useState } from 'react'

const monthLabel = (m: string) =>
  new Date(m + '-01T00:00:00').toLocaleDateString('en-GB', { month: 'short' })

type Tip = { x: number; y: number; text: string } | null

/** Enquiries received vs won per month: grouped bars, value-labelled. */
export function MonthlyChart({ data }: { data: { month: string; enquiries: number; won: number }[] }) {
  const [tip, setTip] = useState<Tip>(null)
  const W = 560, H = 200, PAD_L = 8, PAD_B = 24, PAD_T = 18
  const max = Math.max(1, ...data.map(d => d.enquiries))
  const slot = (W - PAD_L) / data.length
  const bw = Math.min(22, slot / 3.2)
  const y = (v: number) => H - PAD_B - ((H - PAD_B - PAD_T) * v) / max

  // Bars with a 4px rounded top anchored flat to the baseline.
  const bar = (x: number, v: number) => {
    const top = y(v), base = H - PAD_B
    if (v === 0) return `M${x} ${base}h${bw}`
    const r = Math.min(4, base - top)
    return `M${x} ${base}V${top + r}q0 -${r} ${r} -${r}h${bw - 2 * r}q${r} 0 ${r} ${r}V${base}Z`
  }

  return (
    <div className="chart" onMouseLeave={() => setTip(null)}>
      <div className="legend" style={{ marginBottom: '0.5rem' }}>
        <span><i style={{ background: 'var(--chart-a)' }} />Enquiries received</span>
        <span><i style={{ background: 'var(--chart-b)' }} />Won</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Enquiries and wins per month, last six months">
        {[0.5, 1].map(f => (
          <line key={f} x1={PAD_L} x2={W} y1={y(max * f)} y2={y(max * f)} stroke="var(--line)" strokeDasharray="2 4" />
        ))}
        <line x1={PAD_L} x2={W} y1={H - PAD_B} y2={H - PAD_B} stroke="var(--line-strong)" />
        {data.map((d, i) => {
          const cx = PAD_L + slot * i + slot / 2
          const xa = cx - bw - 1, xb = cx + 1
          return (
            <g key={d.month}>
              <path d={bar(xa, d.enquiries)} fill="var(--chart-a)" stroke={d.enquiries ? undefined : 'var(--chart-a)'} />
              <path d={bar(xb, d.won)} fill="var(--chart-b)" stroke={d.won ? undefined : 'var(--chart-b)'} />
              <text x={xa + bw / 2} y={y(d.enquiries) - 5} textAnchor="middle" className="val">{d.enquiries}</text>
              <text x={xb + bw / 2} y={y(d.won) - 5} textAnchor="middle" className="val">{d.won}</text>
              <text x={cx} y={H - 7} textAnchor="middle">{monthLabel(d.month)}</text>
              <rect
                x={cx - slot / 2} y={PAD_T - 10} width={slot} height={H - PAD_T}
                fill="transparent"
                onMouseMove={() => setTip({
                  x: (cx / W) * 100, y: (y(d.enquiries) / H) * 100,
                  text: `${monthLabel(d.month)}: ${d.enquiries} received, ${d.won} won`,
                })}
              />
            </g>
          )
        })}
      </svg>
      {tip && <div className="tooltip" style={{ left: `${tip.x}%`, top: `calc(${tip.y}% + 1.5rem)` }}>{tip.text}</div>}
      <details className="tableview">
        <summary>Show as table</summary>
        <table className="spec">
          <thead><tr><th>Month</th><th className="num">Received</th><th className="num">Won</th></tr></thead>
          <tbody>{data.map(d => <tr key={d.month}><td>{monthLabel(d.month)}</td><td className="num">{d.enquiries}</td><td className="num">{d.won}</td></tr>)}</tbody>
        </table>
      </details>
    </div>
  )
}

/** Open leads by score band: one series, horizontal bars. */
export function BandChart({ data }: { data: { band: string; count: number }[] }) {
  const max = Math.max(1, ...data.map(d => d.count))
  return (
    <div role="img" aria-label="Open leads by lead score band" style={{ display: 'grid', gap: '0.45rem' }}>
      {[...data].reverse().map((d, i) => (
        <div key={d.band} style={{ display: 'grid', gridTemplateColumns: '64px 1fr 28px', alignItems: 'center', gap: '0.6rem' }} className="small">
          <span className="muted fig" style={{ fontWeight: 500 }}>{d.band}</span>
          <div style={{ height: 14, background: 'var(--surface-2)', borderRadius: 2 }}>
            <div
              title={`${d.count} leads scoring ${d.band}`}
              style={{
                width: `${(d.count / max) * 100}%`, height: '100%', borderRadius: '0 4px 4px 0',
                background: i === 0 ? 'var(--signal)' : 'var(--chart-a)', minWidth: d.count ? 3 : 0,
              }}
            />
          </div>
          <span className="fig">{d.count}</span>
        </div>
      ))}
    </div>
  )
}
