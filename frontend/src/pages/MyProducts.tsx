import { useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, unitMoney, type Product, type ProductIn } from '../api'
import { useLoad } from '../useLoad'

const BLANK: ProductIn = { name: '', category: '', material: '', unit_price: 0, unit: 'piece', description: '' }

export function MyProducts() {
  const { data, error, reload } = useLoad(() => api.myProducts(), [])
  const dialog = useRef<HTMLDialogElement>(null)
  const [editing, setEditing] = useState<Product | null>(null)
  const [form, setForm] = useState<ProductIn>(BLANK)
  const [formError, setFormError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const open = (p: Product | null) => {
    setEditing(p); setFormError(null)
    setForm(p ? { name: p.name, category: p.category, material: p.material, unit_price: p.unit_price, unit: p.unit, description: p.description } : BLANK)
    dialog.current?.showModal()
  }
  const set = (k: keyof ProductIn) => (e: { target: { value: string } }) =>
    setForm(f => ({ ...f, [k]: k === 'unit_price' ? Number(e.target.value) : e.target.value }))

  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      if (editing) await api.updateProduct(editing.id, form); else await api.createProduct(form)
      dialog.current?.close()
      setNotice(editing ? `Saved ${form.name}.` : `Listed ${form.name} in the catalogue.`)
      reload()
    } catch (err) { setFormError((err as Error).message) }
  }

  async function remove(p: Product) {
    if (!confirm(`Remove ${p.name} from the catalogue?`)) return
    try { await api.deleteProduct(p.id); setNotice(`Removed ${p.name}.`); reload() }
    catch (err) { setNotice(null); alert((err as Error).message) }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="title">My products</h1>
          <p className="lede">Parts listed here appear in the catalogue, where buyers can request quotes.</p>
        </div>
        <button className="btn btn-primary" onClick={() => open(null)}>List a product</button>
      </div>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error">{error}</p>}
      {!data ? !error && <p className="loading">Loading products…</p> : data.length === 0 ? (
        <div className="table-wrap empty">
          <p className="h3">You have no products listed</p>
          <p>List your first part so buyers can find it and send you requests.</p>
          <button className="btn" onClick={() => open(null)}>List a product</button>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="spec">
            <thead><tr><th>Part</th><th>Category</th><th>Material</th><th className="num">List price</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {data.map(p => (
                <tr key={p.id}>
                  <td><Link to={`/catalogue/${p.id}`} className="rowlink">{p.name}</Link></td>
                  <td>{p.category}</td>
                  <td>{p.material}</td>
                  <td className="num"><span className="fig">{unitMoney(p.unit_price)}</span> <span className="small muted">/ {p.unit}</span></td>
                  <td className="num" style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-quiet" onClick={() => open(p)}>Edit</button>
                    <button className="btn btn-quiet btn-danger" onClick={() => remove(p)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <dialog ref={dialog} className="sheet" aria-labelledby="pf-h">
        <form onSubmit={save}>
          <h2 className="h2" id="pf-h">{editing ? `Edit ${editing.name}` : 'List a product'}</h2>
          {formError && <p className="error" role="alert">{formError}</p>}
          <div className="field">
            <label htmlFor="pn">Part name</label>
            <input id="pn" className="input" required value={form.name} onChange={set('name')} placeholder="Hex bolt M12 x 60" />
          </div>
          <div className="row-fields">
            <div className="field">
              <label htmlFor="pc">Category</label>
              <input id="pc" className="input" required value={form.category} onChange={set('category')} placeholder="Fasteners" />
            </div>
            <div className="field">
              <label htmlFor="pm">Material</label>
              <input id="pm" className="input" required value={form.material} onChange={set('material')} placeholder="Stainless Steel 304" />
            </div>
          </div>
          <div className="row-fields">
            <div className="field">
              <label htmlFor="pp">List price (USD)</label>
              <input id="pp" className="input fig" type="number" step="0.01" min="0.01" required value={form.unit_price || ''} onChange={set('unit_price')} />
            </div>
            <div className="field">
              <label htmlFor="pu">Sold per</label>
              <select id="pu" className="input" value={form.unit} onChange={set('unit')}>
                {['piece', 'kg', 'metre', 'sheet', 'kit', 'litre'].map(u => <option key={u}>{u}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="pd">Description</label>
            <textarea id="pd" className="input" value={form.description} onChange={set('description')} placeholder="Standards, finish, certificates…" />
          </div>
          <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-quiet" onClick={() => dialog.current?.close()}>Cancel</button>
            <button className="btn btn-primary">{editing ? 'Save changes' : 'List product'}</button>
          </div>
        </form>
      </dialog>
    </>
  )
}
