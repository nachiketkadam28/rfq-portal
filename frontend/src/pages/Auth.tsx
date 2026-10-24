import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { homeFor, useAuth } from '../auth'
import { BrandMark } from '../components/Shell'

// The hosted admin has its own password (SEED_ADMIN_PASSWORD), so only offer it locally.
const DEMO = [
  ['Buyer', 'procurement@kestrel.example.com'],
  ['Supplier', 'sales@forgeline.example.com'],
  ...(import.meta.env.DEV ? [['Admin', 'admin@rfq.example.com']] : []),
] as const

function Side() {
  return (
    <aside className="auth-side">
      <Link to="/catalogue" className="brand" style={{ padding: 0 }}><BrandMark />RFQ Desk</Link>
      <div>
        <h1 className="title">Quotes for industrial parts, without the email chains.</h1>
        <p className="lede">
          Buyers send one request per part with quantity and deadline. Suppliers see every request
          ranked by how likely it is to become an order, and reply with a priced quote.
        </p>
      </div>
      <p className="small muted">Fasteners, valves, pipe, sealing and raw stock from verified suppliers.</p>
    </aside>
  )
}

export function Login() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const r = await api.login(email, password)
      signIn(r.access_token, r.user)
      navigate((location.state as { from?: string })?.from ?? homeFor(r.user), { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <Side />
      <section className="auth-form">
        <h2 className="h2">Sign in</h2>
        <form onSubmit={submit}>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="field">
            <label htmlFor="email">Work email</label>
            <input id="email" className="input" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pw">Password</label>
            <input id="pw" className="input" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <button className="btn btn-primary" style={{ width: '100%' }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p className="small muted" style={{ marginTop: '1rem' }}>New here? <Link to="/register">Create an account</Link></p>
        <div className="demo">
          Demo accounts use the password <b>demo1234</b>. Fill in:{' '}
          {DEMO.map(([label, addr], i) => (
            <span key={addr}>
              <button type="button" onClick={() => { setEmail(addr); setPassword('demo1234') }}>{label}</button>
              {i < DEMO.length - 1 ? ', ' : ''}
            </span>
          ))}
        </div>
      </section>
    </div>
  )
}

export function Register() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', company: '', email: '', password: '', role: 'buyer' as 'buyer' | 'supplier' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const r = await api.register(form)
      signIn(r.access_token, r.user)
      navigate(homeFor(r.user), { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <Side />
      <section className="auth-form">
        <h2 className="h2">Create an account</h2>
        <form onSubmit={submit}>
          {error && <p className="error" role="alert">{error}</p>}
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="small" style={{ fontWeight: 600, marginBottom: '0.3rem' }}>I want to</legend>
            <div className="rolepick">
              <label>
                <input type="radio" name="role" value="buyer" checked={form.role === 'buyer'} onChange={set('role')} />
                <b>Buy parts</b><span>Request quotes from suppliers</span>
              </label>
              <label>
                <input type="radio" name="role" value="supplier" checked={form.role === 'supplier'} onChange={set('role')} />
                <b>Sell parts</b><span>List products and answer RFQs</span>
              </label>
            </div>
          </fieldset>
          <div className="row-fields">
            <div className="field">
              <label htmlFor="name">Your name</label>
              <input id="name" className="input" required minLength={2} autoComplete="name" value={form.name} onChange={set('name')} />
            </div>
            <div className="field">
              <label htmlFor="company">Company</label>
              <input id="company" className="input" required minLength={2} autoComplete="organization" value={form.company} onChange={set('company')} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="remail">Work email</label>
            <input id="remail" className="input" type="email" required autoComplete="email" value={form.email} onChange={set('email')} />
          </div>
          <div className="field">
            <label htmlFor="rpw">Password</label>
            <input id="rpw" className="input" type="password" required minLength={6} autoComplete="new-password" value={form.password} onChange={set('password')} />
            <span className="hint">At least 6 characters.</span>
          </div>
          <button className="btn btn-primary" style={{ width: '100%' }} disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
        </form>
        <p className="small muted" style={{ marginTop: '1rem' }}>Already registered? <Link to="/login">Sign in</Link></p>
      </section>
    </div>
  )
}
