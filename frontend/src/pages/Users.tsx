import { useState } from 'react'
import { api, shortDate, type Role } from '../api'
import { useLoad } from '../useLoad'

export function Users() {
  const { data, error } = useLoad(() => api.users(), [])
  const [role, setRole] = useState<Role | 'all'>('all')
  const rows = data?.filter(u => role === 'all' || u.role === role)

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="title">Accounts</h1>
          <p className="lede">Everyone registered on the portal, newest first.</p>
        </div>
        <div className="segmented" role="group" aria-label="Filter by role">
          {(['all', 'buyer', 'supplier', 'admin'] as const).map(r => (
            <button key={r} aria-pressed={role === r} onClick={() => setRole(r)}>{r === 'all' ? 'All' : r[0].toUpperCase() + r.slice(1) + 's'}</button>
          ))}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {!rows ? <p className="loading">Loading accounts…</p> : (
        <div className="table-wrap">
          <table className="spec">
            <thead><tr><th>Name</th><th>Company</th><th>Email</th><th>Role</th><th className="num">Products</th><th className="num">Requests</th><th>Joined</th></tr></thead>
            <tbody>
              {rows.map(u => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.name}</td>
                  <td>{u.company}</td>
                  <td className="muted">{u.email}</td>
                  <td style={{ textTransform: 'capitalize' }}>{u.role}</td>
                  <td className="num fig">{u.role === 'supplier' ? u.products : ''}</td>
                  <td className="num fig">{u.role === 'buyer' ? u.enquiries : ''}</td>
                  <td>{shortDate(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
