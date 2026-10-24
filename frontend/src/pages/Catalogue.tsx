import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, unitMoney } from '../api'
import { useAuth } from '../auth'
import { useLoad } from '../useLoad'

export function Catalogue() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const facets = useLoad(() => api.facets(), [])
  const products = useLoad(() => api.products(Object.fromEntries(params)), [params.toString()])

  // Debounce the search box into the URL so results are shareable.
  useEffect(() => {
    const t = setTimeout(() => {
      const next = new URLSearchParams(params)
      if (q) next.set('q', q); else next.delete('q')
      if (next.toString() !== params.toString()) setParams(next, { replace: true })
    }, 250)
    return () => clearTimeout(t)
  }, [q, params, setParams])

  const toggle = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (next.get(key) === value) next.delete(key); else next.set(key, value)
    setParams(next)
  }

  const list = products.data
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="title">Catalogue</h1>
          <p className="lede">Pick a part to see its specification and request a quote from the supplier.</p>
        </div>
      </div>
      <div className="catalogue">
        <aside className="filters" aria-label="Filters">
          <div className="search">
            <svg viewBox="0 0 16 16" aria-hidden><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="m11 11 3.5 3.5" stroke="currentColor" strokeWidth="1.6" /></svg>
            <label htmlFor="q" className="sr-only">Search parts</label>
            <input id="q" className="input" placeholder="Bolt, flange, PTFE…" value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <h3>Category</h3>
          {facets.data?.categories.map(f => (
            <button key={f.name} className="facet" aria-pressed={params.get('category') === f.name} onClick={() => toggle('category', f.name)}>
              <span>{f.name}</span><span className="fig">{f.count}</span>
            </button>
          ))}
          <h3>Material</h3>
          {facets.data?.materials.map(f => (
            <button key={f.name} className="facet" aria-pressed={params.get('material') === f.name} onClick={() => toggle('material', f.name)}>
              <span>{f.name}</span><span className="fig">{f.count}</span>
            </button>
          ))}
        </aside>
        <section aria-live="polite">
          {products.error && <p className="error">{products.error}</p>}
          {!list ? !products.error && <p className="loading">Loading parts…</p> : (
            <>
              <p className="small muted" style={{ margin: '0 0 0.5rem' }}>
                {list.length} {list.length === 1 ? 'part' : 'parts'}
                {params.size > 0 && <> <button className="btn-quiet" style={{ border: 0, background: 'none', cursor: 'pointer', textDecoration: 'underline', padding: 0 }} onClick={() => { setQ(''); setParams({}) }}>Clear filters</button></>}
              </p>
              <div className="table-wrap">
                {list.length === 0 ? (
                  params.size > 0 ? (
                    <div className="empty">
                      <p className="h3">No parts match these filters</p>
                      <p>Try a broader search term or remove a filter.</p>
                    </div>
                  ) : (
                    <div className="empty">
                      <p className="h3">No parts listed yet</p>
                      <p>Parts appear here once suppliers add them. Suppliers can create an account and list their first product.</p>
                    </div>
                  )
                ) : list.map(p => (
                  <Link key={p.id} to={`/catalogue/${p.id}`} className="part">
                    <span className="part-name">{p.name}</span>
                    <span className="part-price"><span className="fig">{unitMoney(p.unit_price)}</span><span className="small muted">per {p.unit}</span></span>
                    <span className="part-spec">{p.material}, {p.category.toLowerCase()} from {p.supplier_company}</span>
                  </Link>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}

export function ProductPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const { data: p, error } = useLoad(() => api.product(Number(id)), [id])
  const [qty, setQty] = useState('')
  const [date, setDate] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  if (error) return <p className="error">{error}</p>
  if (!p) return <p className="loading">Loading part…</p>

  const estimate = Number(qty) > 0 ? Number(qty) * p.unit_price : null

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setFormError(null)
    try {
      const enq = await api.createEnquiry({ product_id: p!.id, quantity: Number(qty), required_by: date || null, message })
      navigate(`/enquiries/${enq.id}`, { state: { sent: true } })
    } catch (err) {
      setFormError((err as Error).message)
    } finally { setBusy(false) }
  }

  const today = new Date().toISOString().slice(0, 10)

  return (
    <>
      <Link to="/catalogue" className="crumb">Back to catalogue</Link>
      <div className="split">
        <div>
          <p className="muted" style={{ margin: '0 0 0.25rem' }}>{p.category}</p>
          <h1 className="title">{p.name}</h1>
          <p className="lede">{p.description || 'No description provided.'}</p>
          <dl className="specsheet" style={{ marginTop: '1.5rem' }}>
            <dt>Material</dt><dd>{p.material}</dd>
            <dt>List price</dt><dd><span className="fig">{unitMoney(p.unit_price)}</span> per {p.unit}</dd>
            <dt>Supplier</dt><dd>{p.supplier_company}</dd>
            <dt>Part number</dt><dd className="fig">RFQ-{String(p.id).padStart(5, '0')}</dd>
          </dl>
        </div>
        <section className="panel" aria-labelledby="rfq-h">
          <h2 className="h2" id="rfq-h">Request a quote</h2>
          {!user ? (
            <>
              <p className="muted">Sign in with a buyer account to send this supplier a request.</p>
              <Link to="/login" state={{ from: `/catalogue/${p.id}` }} className="btn btn-primary">Sign in to request a quote</Link>
            </>
          ) : user.role !== 'buyer' ? (
            <p className="muted">Only buyer accounts can request quotes. You are signed in as a {user.role}.</p>
          ) : (
            <form onSubmit={submit}>
              {formError && <p className="error" role="alert">{formError}</p>}
              <div className="row-fields">
                <div className="field">
                  <label htmlFor="qty">Quantity ({p.unit}s)</label>
                  <input id="qty" className="input fig" type="number" min={1} required value={qty} onChange={e => setQty(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="by">Needed by</label>
                  <input id="by" className="input" type="date" min={today} value={date} onChange={e => setDate(e.target.value)} />
                </div>
              </div>
              <div className="field">
                <label htmlFor="msg">Requirements</label>
                <textarea id="msg" className="input" value={message} onChange={e => setMessage(e.target.value)} placeholder="Certificates, inspection, delivery terms, packing…" />
                <span className="hint">Specific requests get faster, more accurate quotes.</span>
              </div>
              {estimate !== null && <p className="small muted">At list price this order is about <b className="fig">{unitMoney(estimate)}</b>. The supplier will confirm the final price.</p>}
              <button className="btn btn-primary" disabled={busy}>{busy ? 'Sending…' : 'Send request'}</button>
            </form>
          )}
        </section>
      </div>
    </>
  )
}
