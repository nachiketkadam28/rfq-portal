import { useEffect, useState } from 'react'

// Lead score drawn as a pressure gauge: 240° sweep, 80–100 is the "hot" zone.
const CX = 100
const CY = 100
const SWEEP = 240
const angleFor = (v: number) => -SWEEP / 2 + (SWEEP * Math.max(0, Math.min(100, v))) / 100

function polar(r: number, deg: number) {
  const rad = (deg * Math.PI) / 180
  return [CX + r * Math.sin(rad), CY - r * Math.cos(rad)] as const
}

function arc(r: number, from: number, to: number) {
  const [x1, y1] = polar(r, angleFor(from))
  const [x2, y2] = polar(r, angleFor(to))
  const large = ((to - from) / 100) * SWEEP > 180 ? 1 : 0
  return `M${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2}`
}

export function Gauge({ value, size = 220, mini = false }: { value: number; size?: number; mini?: boolean }) {
  // Start at zero and swing to the value once, so the reading registers.
  const [shown, setShown] = useState(mini ? value : 0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(value))
    return () => cancelAnimationFrame(id)
  }, [value])

  const ticks = []
  for (let v = 0; v <= 100; v += mini ? 10 : 5) {
    const major = v % 20 === 0
    const [x1, y1] = polar(mini ? 70 : 78, angleFor(v))
    const [x2, y2] = polar(major ? (mini ? 56 : 66) : 72, angleFor(v))
    ticks.push(<line key={v} x1={x1} y1={y1} x2={x2} y2={y2} className={`tick${major ? ' major' : ''}`} strokeWidth={major ? 2 : 1} />)
    if (major && !mini) {
      const [lx, ly] = polar(54, angleFor(v))
      ticks.push(<text key={`l${v}`} x={lx} y={ly + 3} textAnchor="middle" className="label">{v}</text>)
    }
  }

  return (
    <svg
      className="gauge"
      viewBox={mini ? '14 14 172 150' : '0 0 200 172'}
      width={size}
      role="img"
      aria-label={`Lead score ${Math.round(value)} out of 100`}
    >
      <circle cx={CX} cy={CY} r={mini ? 84 : 92} className="face" strokeWidth={mini ? 6 : 3} />
      <path d={arc(mini ? 77 : 82, 80, 100)} stroke="var(--signal)" strokeWidth={mini ? 12 : 8} fill="none" />
      {ticks}
      <g style={{ transform: `rotate(${angleFor(shown)}deg)`, transformOrigin: `${CX}px ${CY}px`, transformBox: 'view-box' }} className="needle">
        <polygon points={mini ? `${CX - 7},${CY} ${CX},${CY - 70} ${CX + 7},${CY}` : `${CX - 4},${CY} ${CX},${CY - 74} ${CX + 4},${CY}`} />
      </g>
      <circle cx={CX} cy={CY} r={mini ? 12 : 7} fill="var(--ink)" />
      {!mini && (
        <>
          <text x={CX} y={CY + 46} textAnchor="middle" className="readout-num" fontSize="30">{Math.round(value)}</text>
          <text x={CX} y={CY + 60} textAnchor="middle" className="label">likelihood to convert</text>
        </>
      )}
    </svg>
  )
}
