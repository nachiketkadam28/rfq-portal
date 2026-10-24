import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money, type Status } from '../api'
import { useAuth } from '../auth'
import { BandChart, MonthlyChart } from '../components/Charts'
import { Gauge } from '../components/Gauge'
import { StatusTag } from '../components/StatusTag'
import { useLoad } from '../useLoad'

const STAGE_COLOR: Record<Status, string> = {
  new: 'var(--st-new)', quoted: 'var(--st-quoted)', won: 'var(--st-won)', lost: 'var(--st-lost)',
}

export function Dashboard() {
  const { user } = useAuth()
  const { data: d, error } = useLoad(() => api.dashboard(), [])
  const [model, setModel] = useState<{ auc: number; training_rows: number; real_outcomes: number } | null>(null)
  const [training, setTraining] = useState(false)

  if (error) return <p className="error">{error}</p>
  if (!d) return <p className="loading">Loading overview…</p>

  const isAdmin = user!.role === 'admin'
  const sc = d.status_counts

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="title">{isAdmin ? 'Portal overview' : user!.company}</h1>
          <p className="lede">
            {isAdmin
              ? `${d.users?.supplier} suppliers, ${d.users?.buyer} buyers and ${d.products} listed parts.`
              : `${sc.new} new ${sc.new === 1 ? 'request needs' : 'requests need'} a quote, and ${sc.quoted} ${sc.quoted === 1 ? 'quote is' : 'quotes are'} waiting on the buyer.`}
          </p>
        </div>
        <Link to="/enquiries?sort=score" className="btn btn-primary">{isAdmin ? 'View all requests' : 'Work the hottest leads'}</Link>
      </div>

      <div className="readouts">
        <div className="readout"><span className="fig">{money(d.pipeline_value)}</span><span className="muted">open pipeline</span></div>
        <div className="readout"><span className="fig">{money(d.won_value)}</span><span className="muted">won to date</span></div>
        <div className="readout"><span className="fig">{d.win_rate === null ? 'None yet' : `${d.win_rate}%`}</span><span className="muted">win rate on closed requests</span></div>
        <div className="readout"><span className="fig">{d.avg_open_score ?? 'None'}</span><span className="muted">average score of open leads</span></div>
      </div>

      <section className="panel" style={{ marginBottom: '1.25rem' }} aria-labelledby="pipe-h">
        <h2 className="h2" id="pipe-h" style={{ marginBottom: 0 }}>Where {d.total} requests stand</h2>
        <div className="pipeline" role="img" aria-label={`${sc.new} new, ${sc.quoted} quoted, ${sc.won} won, ${sc.lost} lost`}>
          {(Object.keys(sc) as Status[]).map(s => sc[s] > 0 && (
            <span key={s} style={{ flex: sc[s], background: STAGE_COLOR[s] }} title={`${sc[s]} ${s}`} />
          ))}
        </div>
        <div className="legend">
          {(Object.keys(sc) as Status[]).map(s => (
            <Link key={s} to={`/enquiries?status=${s}`} style={{ textDecoration: 'none' }}>
              <StatusTag status={s} /> <span className="fig" style={{ color: 'var(--ink)', marginLeft: 4 }}>{sc[s]}</span>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid cols-2" style={{ marginBottom: '1.25rem' }}>
        <section className="panel" aria-labelledby="hot-h">
          <h2 className="h2" id="hot-h">Hottest open leads</h2>
          {d.hot_leads?.length ? (
            <table className="spec">
              <tbody>
                {d.hot_leads.map(e => (
                  <tr key={e.id}>
                    <td style={{ width: 56, paddingLeft: 0 }}><Gauge value={e.lead_score ?? 0} size={40} mini /></td>
                    <td>
                      <Link to={`/enquiries/${e.id}`} className="rowlink">{e.buyer_company}</Link>
                      <div className="small muted">{e.quantity.toLocaleString()} × {e.product_name}</div>
                    </td>
                    <td className="num"><span className="fig" style={{ fontSize: '1.2rem' }}>{Math.round(e.lead_score ?? 0)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No open leads. New requests will show up here ranked by score.</p>}
        </section>
        <section className="panel" aria-labelledby="bands-h">
          <h2 className="h2" id="bands-h">Open leads by score</h2>
          {d.score_bands && <BandChart data={d.score_bands} />}
          <p className="small muted" style={{ marginBottom: 0 }}>Scores of 80 and above sit in the gauge’s yellow zone. Quote these first.</p>
        </section>
      </div>

      <div className="grid cols-2">
        <section className="panel" aria-labelledby="month-h">
          <h2 className="h2" id="month-h">Requests and wins by month</h2>
          <MonthlyChart data={d.monthly} />
        </section>
        <section className="panel" aria-labelledby="top-h">
          <h2 className="h2" id="top-h">Most requested parts</h2>
          {d.top_products?.length ? (
            <table className="spec">
              <thead><tr><th>Part</th><th className="num">Requests</th><th className="num">Won</th></tr></thead>
              <tbody>
                {d.top_products.map(p => (
                  <tr key={p.product}><td>{p.product}</td><td className="num fig">{p.enquiries}</td><td className="num fig">{p.won}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No requests yet.</p>}
        </section>
      </div>

      {isAdmin && (
        <section className="panel" style={{ marginTop: '1.25rem' }} aria-labelledby="model-h">
          <h2 className="h2" id="model-h">Lead scoring model</h2>
          <p className="muted" style={{ maxWidth: '65ch' }}>
            Retraining adds every won and lost request to the training data, then rescores all open requests.
            Do this after a batch of requests has closed.
          </p>
          {model && (
            <p className="notice" role="status">
              Retrained on {model.training_rows.toLocaleString()} rows, including {model.real_outcomes} real outcomes.
              Ranking accuracy (AUC) on held-out data: <b className="fig">{model.auc}</b>.
            </p>
          )}
          <button className="btn" disabled={training} onClick={async () => {
            setTraining(true)
            try { setModel(await api.retrain()) } finally { setTraining(false) }
          }}>{training ? 'Retraining…' : 'Retrain and rescore'}</button>
        </section>
      )}
    </>
  )
}
