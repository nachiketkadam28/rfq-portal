import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { Role } from './api'
import { AuthProvider, homeFor, useAuth } from './auth'
import { Shell } from './components/Shell'
import { Login, Register } from './pages/Auth'
import { Catalogue, ProductPage } from './pages/Catalogue'
import { Dashboard } from './pages/Dashboard'
import { Enquiries, EnquiryDetail } from './pages/Enquiries'
import { MyProducts } from './pages/MyProducts'
import { Users } from './pages/Users'

function Guard({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <p className="loading">Loading…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />
  return <>{children}</>
}

function Home() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={homeFor(user)} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<Shell />}>
            <Route index element={<Home />} />
            <Route path="/catalogue" element={<Catalogue />} />
            <Route path="/catalogue/:id" element={<ProductPage />} />
            <Route path="/enquiries" element={<Guard><Enquiries /></Guard>} />
            <Route path="/enquiries/:id" element={<Guard><EnquiryDetail /></Guard>} />
            <Route path="/dashboard" element={<Guard roles={['supplier', 'admin']}><Dashboard /></Guard>} />
            <Route path="/my-products" element={<Guard roles={['supplier']}><MyProducts /></Guard>} />
            <Route path="/admin/users" element={<Guard roles={['admin']}><Users /></Guard>} />
            <Route path="*" element={<div className="empty"><p className="h3">This page does not exist</p><a href="/">Go to the start page</a></div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
