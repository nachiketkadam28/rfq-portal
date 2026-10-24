import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, money, shortDate, unitMoney, type Enquiry, type Status } from '../api'
import { useAuth } from '../auth'
import { Gauge } from '../components/Gauge'
import { StatusTag } from '../components/StatusTag'
import { useLoad } from '../useLoad'

const FILTERS: (Status | 'all')[] = ['all', 'new', 'quoted', 'won', 'lost']
const latestQuote = (e: Enquiry) => e.quotations.at(-1)

export function Enquiries() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') ?? 'all') as Status | 'all'
  const isBuyer = user!.role === 'buyer'
  const sort = isBuyer ? 'recent' : (params.get('sort') ?? 'score')
  const { data, error } = useLoad(
    () => api.enquiries({ ...(status !== 'all' && { status }), sort }),
    [status, sort],
  )
  const update = (k: string, v: string) => { const n = new URLSearchParams(params); n.set(k, v); setParams(n, { replace: true }) }

  const title = isBuyer ? 'My requests for quotation' : user!.role === 'admin' ? 'All requests' : 'Leads'
  const lede = isBuyer
    ? 'Every quote you have asked for, with the supplier’s latest reply.'
    : 'Incoming requests for your products. The gauge shows how likely each one is to become an order.'

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="title">{title}</h1>
          <p className="lede">{lede}</p>
        </div>
        {isBuyer && <Link to="/catalogue" className="btn btn-primary">Request a new quote</Link>}
      </div>
      <div className="btn-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div className="segmented" role="group" aria-label="Filter by status">
          {FILTERS.map(f => (
            <button key={f} aria-pressed={status === f} onClick={() => update('status', f === 'all' ? '' : f)}>
              {f === 'all' ? 'All' : f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        {!isBuyer && (
          <div className="segmented" role="group" aria-label="Sort">
            <button aria-pressed={sort === 'score'} onClick={() => update('sort', 'score')}>Hottest first</button>
            <button aria-pressed={sort === 'recent'} onClick={() => update('sort', 'recent')}>Newest first</button>
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {!data ? !error && <p className="loading">Loading requests…</p> : data.length === 0 ? (
        <div className="table-wrap empty">
          <p className="h3">{status === 'all' ? 'No requests yet' : `No ${status} requests`}</p>
          <p>{isBuyer ? 'Find a part in the catalogue and send your first request.' : 'Requests appear here as soon as a buyer asks about one of your products.'}</p>
          {isBuyer && <Link to="/catalogue" className="btn">Browse the catalogue</Link>}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="spec">
            <thead>
              <tr>
                {!isBuyer && <th style={{ width: 120 }}>Lead score</th>}
                <th>Part</th>
                <th className="hide-sm">{isBuyer ? 'Supplier' : 'Buyer'}</th>
                <th className="num">Quantity</th>
                <th className="num">{isBuyer ? 'Quoted price' : 'Value at list'}</th>
                <th className="hide-sm">Needed by</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map(e => {
                const q = latestQuote(e)
                return (
                  <tr key={e.id} className="clickable" onClick={() => navigate(`/enquiries/${e.id}`)}>
                    {!isBuyer && (
                      <td>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Gauge value={e.lead_score ?? 0} size={38} mini />
                          <span className="fig" style={{ fontSize: '1.15rem' }}>{Math.round(e.lead_score ?? 0)}</span>
                        </span>
                      </td>
                    )}
                    <td>
                      <Link to={`/enquiries/${e.id}`} className="rowlink" onClick={ev => ev.stopPropagation()}>{e.product_name}</Link>
                      <div className="small muted"><span className="show-sm">{isBuyer ? e.supplier_company : e.buyer_company}. </span>Received {shortDate(e.created_at)}</div>
                    </td>
                    <td className="hide-sm">{isBuyer ? e.supplier_company : e.buyer_company}</td>
                    <td className="num fig">{e.quantity.toLocaleString()}</td>
                    <td className="num fig">
                      {isBuyer ? (q ? unitMoney(q.price_per_unit) : <span className="muted">Pending</span>) : money(e.quantity * e.list_price)}
                    </td>
                    <td className="hide-sm">{e.required_by ? shortDate(e.required_by) : <span className="muted">Flexible</span>}</td>
                    <td><StatusTag status={e.status} buyerView={isBuyer} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function EnquiryDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const location = useLocation()
  const { data: e, error, set } = useLoad(() => api.enquiry(Number(id)), [id])
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>((location.state as { sent?: boolean })?.sent ? 'Request sent. You will see the supplier’s quote here.' : null)

  if (error) return <p className="error">{error}</p>
  if (!e) return <p className="loading">Loading request…</p>

  const isBuyer = user!.role === 'buyer'
  const isSupplier = user!.role === 'supplier'
  const open = e.status === 'new' || e.status === 'quoted'
  const q = latestQuote(e)

  async function act(fn: () => Promise<Enquiry>, done: string) {
    setActionError(null)
    try { set(await fn()); setNotice(done) } catch (err) { setActionError((err as Error).message) }
  }

  return (
    <>
      <Link to="/enquiries" className="crumb">Back to {isBuyer ? 'my requests' : 'leads'}</Link>
      <div className="page-head">
        <div>
          <p className="muted" style={{ margin: '0 0 0.25rem' }}>RFQ {e.id} for {isBuyer ? e.supplier_company : `${e.buyer_name}, ${e.buyer_company}`}</p>
          <h1 className="title">{e.product_name}</h1>
        </div>
        <StatusTag status={e.status} buyerView={isBuyer} />
      </div>
      {notice && <p className="notice" role="status">{notice}</p>}
      {actionError && <p className="error" role="alert">{actionError}</p>}

      <div className={isBuyer ? 'grid' : 'split'} style={isBuyer ? { maxWidth: 760 } : undefined}>
        <div className="grid">
          <dl className="specsheet">
            <dt>Quantity</dt><dd><span className="fig">{e.quantity.toLocaleString()}</span> {e.product_unit}s</dd>
            <dt>Needed by</dt><dd>{e.required_by ? shortDate(e.required_by) : 'No deadline given'}</dd>
            <dt>List price</dt><dd><span className="fig">{unitMoney(e.list_price)}</span> per {e.product_unit}, about <span className="fig">{money(e.list_price * e.quantity)}</span> in total</dd>
            <dt>Category</dt><dd>{e.product_category}</dd>
          </dl>

          <section className="panel">
            <h2 className="h2">History</h2>
            <ol className="thread">
              <li>
                <b>{isBuyer ? 'You' : e.buyer_name} sent the request</b> <span className="small muted">{shortDate(e.created_at)}</span>
                <p style={{ margin: '0.3rem 0 0', maxWidth: '65ch' }}>{e.message || <span className="muted">No additional requirements.</span>}</p>
              </li>
              {e.quotations.map(qt => (
                <li key={qt.id} className="quote">
                  <b>{isSupplier ? 'You' : e.supplier_company} quoted</b> <span className="small muted">{shortDate(qt.created_at)}</span>
                  <div className="quote-card">
                    <div className="btn-row" style={{ gap: '1.75rem' }}>
                      <div><span className="fig">{unitMoney(qt.price_per_unit)}</span><div className="small muted">per {e.product_unit}</div></div>
                      <div><span className="fig">{money(qt.price_per_unit * e.quantity)}</span><div className="small muted">order total</div></div>
                      <div><span className="fig">{qt.delivery_days} days</span><div className="small muted">delivery</div></div>
                    </div>
                    {qt.notes && <p className="small" style={{ margin: '0.6rem 0 0' }}>{qt.notes}</p>}
                  </div>
                </li>
              ))}
              {!open && (
                <li><b>{e.status === 'won' ? (isBuyer ? 'You accepted the quote' : 'Order won') : (isBuyer ? 'You declined the quote' : 'Marked as lost')}</b></li>
              )}
            </ol>
            {isBuyer && e.status === 'quoted' && q && (
              <div className="btn-row" style={{ marginTop: '0.5rem' }}>
                <button className="btn btn-primary" onClick={() => act(() => api.setStatus(e.id, 'won'), 'Quote accepted. The supplier will confirm the order.')}>Accept quote</button>
                <button className="btn" onClick={() => act(() => api.setStatus(e.id, 'lost'), 'Quote declined.')}>Decline</button>
              </div>
            )}
          </section>

          {isSupplier && open && <QuoteForm enquiry={e} onSent={next => { set(next); setNotice('Quote sent to the buyer.') }} />}
        </div>

        {!isBuyer && e.lead_score !== null && (
          <aside className="panel" aria-labelledby="score-h">
            <h2 className="h2" id="score-h">Lead score</h2>
            <div style={{ display: 'flex', justifyContent: 'center' }}><Gauge value={e.lead_score} /></div>
            <h3 className="h3" style={{ marginTop: '0.5rem' }}>What moved the score</h3>
            <ul className="reasons">
              {e.score_reasons.map(r => {
                const w = Math.min(50, Math.abs(r.impact) * 30)
                return (
                  <li key={r.feature}>
                    <span>{r.feature} <span className="muted small">{r.impact >= 0 ? 'raises it' : 'lowers it'}</span></span>
                    <span className="impact" aria-hidden><span className={r.impact >= 0 ? 'up' : 'down'} style={{ width: `${w}%` }} /></span>
                  </li>
                )
              })}
            </ul>
            <p className="small muted" style={{ marginBottom: 0 }}>Scored when the request arrived, from order size, deadline, how detailed the request is, and this buyer’s history with suppliers on the portal.</p>
            {isSupplier && open && (
              <div className="btn-row" style={{ marginTop: '1rem', borderTop: '1px solid var(--line)', paddingTop: '1rem' }}>
                <button className="btn" onClick={() => act(() => api.setStatus(e.id, 'won'), 'Marked as won.')}>Mark as won</button>
                <button className="btn btn-danger" onClick={() => act(() => api.setStatus(e.id, 'lost'), 'Marked as lost.')}>Mark as lost</button>
              </div>
            )}
          </aside>
        )}
      </div>
    </>
  )
}

function QuoteForm({ enquiry, onSent }: { enquiry: Enquiry; onSent: (e: Enquiry) => void }) {
  const prev = latestQuote(enquiry)
  const [price, setPrice] = useState(String(prev?.price_per_unit ?? enquiry.list_price))
  const [days, setDays] = useState(String(prev?.delivery_days ?? 14))
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const total = Number(price) * enquiry.quantity
  const discount = enquiry.list_price ? (1 - Number(price) / enquiry.list_price) * 100 : 0

  async function submit(ev: FormEvent) {
    ev.preventDefault()
    setBusy(true); setError(null)
    try {
      onSent(await api.sendQuote(enquiry.id, { price_per_unit: Number(price), delivery_days: Number(days), notes }))
      setNotes('')
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  return (
    <section className="panel">
      <h2 className="h2">{prev ? 'Send a revised quote' : 'Send a quote'}</h2>
      <form onSubmit={submit}>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row-fields">
          <div className="field">
            <label htmlFor="price">Price per {enquiry.product_unit} (USD)</label>
            <input id="price" className="input fig" type="number" step="0.01" min="0.01" max="1000000" required value={price} onChange={e => setPrice(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="days">Delivery (days)</label>
            <input id="days" className="input fig" type="number" min="1" max="3650" required value={days} onChange={e => setDays(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="notes">Terms and notes</label>
          <textarea id="notes" className="input" maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Incoterms, validity, certificates included…" />
        </div>
        {Number(price) > 0 && (
          <p className="small muted">
            Order total <b className="fig">{money(total)}</b>
            {Math.abs(discount) >= 0.5 && <>, {Math.abs(discount).toFixed(1)}% {discount > 0 ? 'below' : 'above'} list price</>}.
          </p>
        )}
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Sending…' : 'Send quote'}</button>
      </form>
    </section>
  )
}
