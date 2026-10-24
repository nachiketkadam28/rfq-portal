export type Role = 'buyer' | 'supplier' | 'admin'
export type Status = 'new' | 'quoted' | 'won' | 'lost'

export interface User { id: number; name: string; company: string; email: string; role: Role }

export interface ProductIn {
  name: string; category: string; material: string; unit_price: number; unit: string; description: string
}
export interface Product extends ProductIn { id: number; supplier_id: number; supplier_company: string | null }

export interface Quotation { id: number; price_per_unit: number; delivery_days: number; notes: string; created_at: string }

export interface Enquiry {
  id: number
  product_id: number
  product_name: string
  product_category: string
  product_unit: string
  list_price: number
  supplier_company: string
  buyer_name: string
  buyer_company: string
  quantity: number
  required_by: string | null
  message: string
  status: Status
  lead_score: number | null
  score_reasons: { feature: string; impact: number }[]
  created_at: string
  quotations: Quotation[]
}

export interface Facet { name: string; count: number }

export interface Dashboard {
  role: Role
  status_counts: Record<Status, number>
  total: number
  win_rate: number | null
  pipeline_value: number
  won_value: number
  monthly: { month: string; enquiries: number; won: number }[]
  avg_open_score?: number | null
  hot_leads?: Enquiry[]
  top_products?: { product: string; enquiries: number; won: number }[]
  score_bands?: { band: string; count: number }[]
  awaiting_decision?: Enquiry[]
  users?: Record<Role, number>
  products?: number
}

export interface AdminUser extends User { created_at: string; products: number; enquiries: number }

const TOKEN_KEY = 'rfq.token'

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable: session lasts until reload */ }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && typeof init.body === 'string') headers.set('Content-Type', 'application/json')
  const res = await fetch(`/api${path}`, { ...init, headers })
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    if (typeof body?.detail === 'string') msg = body.detail
    else if (Array.isArray(body?.detail)) msg = body.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.at(-1)}: ${d.msg}`).join('; ')
    if (res.status === 401 && token) setToken(null)
    throw new ApiError(res.status, msg)
  }
  return body as T
}

const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) })

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST', body: new URLSearchParams({ username: email, password }),
    }),
  register: (data: { name: string; company: string; email: string; password: string; role: 'buyer' | 'supplier' }) =>
    request<{ access_token: string; user: User }>('/auth/register', json('POST', data)),
  me: () => request<User>('/auth/me'),

  products: (params: Record<string, string> = {}) =>
    request<Product[]>(`/products?${new URLSearchParams(params)}`),
  facets: () => request<{ categories: Facet[]; materials: Facet[] }>('/products/facets'),
  product: (id: number) => request<Product>(`/products/${id}`),
  myProducts: () => request<Product[]>('/products/mine'),
  createProduct: (p: ProductIn) => request<Product>('/products', json('POST', p)),
  updateProduct: (id: number, p: ProductIn) => request<Product>(`/products/${id}`, json('PUT', p)),
  deleteProduct: (id: number) => request<void>(`/products/${id}`, { method: 'DELETE' }),

  enquiries: (params: Record<string, string> = {}) =>
    request<Enquiry[]>(`/enquiries?${new URLSearchParams(params)}`),
  enquiry: (id: number) => request<Enquiry>(`/enquiries/${id}`),
  createEnquiry: (data: { product_id: number; quantity: number; required_by: string | null; message: string }) =>
    request<Enquiry>('/enquiries', json('POST', data)),
  sendQuote: (id: number, data: { price_per_unit: number; delivery_days: number; notes: string }) =>
    request<Enquiry>(`/enquiries/${id}/quotations`, json('POST', data)),
  setStatus: (id: number, status: 'won' | 'lost') =>
    request<Enquiry>(`/enquiries/${id}/status`, json('PATCH', { status })),

  dashboard: () => request<Dashboard>('/dashboard'),
  users: () => request<AdminUser[]>('/admin/users'),
  retrain: () => request<{ auc: number; training_rows: number; real_outcomes: number }>('/admin/model/retrain', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: n < 10 ? 2 : 0 })
export const unitMoney = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
export const shortDate = (s: string) =>
  new Date(s.length === 10 ? s + 'T00:00:00' : s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
