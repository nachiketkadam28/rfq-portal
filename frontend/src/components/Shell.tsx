import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function BrandMark() {
  // A hex nut seen end-on.
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden>
      <path d="M12 1.5 21.1 6.75v10.5L12 22.5 2.9 17.25V6.75Z" fill="var(--signal)" stroke="var(--ink)" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="4" fill="var(--surface)" stroke="var(--ink)" strokeWidth="1.5" />
    </svg>
  )
}

const LINKS = {
  buyer: [['/catalogue', 'Catalogue'], ['/enquiries', 'My RFQs']],
  supplier: [['/dashboard', 'Overview'], ['/enquiries', 'Leads'], ['/my-products', 'My products'], ['/catalogue', 'Catalogue']],
  admin: [['/dashboard', 'Overview'], ['/enquiries', 'All RFQs'], ['/admin/users', 'Accounts'], ['/catalogue', 'Catalogue']],
} as const

export function Shell() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const links = user ? LINKS[user.role] : [['/catalogue', 'Catalogue']]

  return (
    <>
      <header className="titleblock">
        <NavLink to="/" className="brand"><BrandMark />RFQ Desk</NavLink>
        <nav className="nav" aria-label="Main">
          {links.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
        </nav>
        <div className="whoami">
          {user ? (
            <>
              <div className="whoami-id small">
                <b>{user.company}</b>
                <span className="muted">{user.name}, {user.role}</span>
              </div>
              <button className="btn btn-quiet" onClick={() => { navigate('/login', { replace: true }); signOut() }}>Sign out</button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="btn btn-quiet">Sign in</NavLink>
              <NavLink to="/register" className="btn">Create account</NavLink>
            </>
          )}
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  )
}
