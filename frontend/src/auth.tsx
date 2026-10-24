import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, SESSION_EXPIRED, setToken, type User } from './api'

interface AuthState {
  user: User | null
  ready: boolean
  expired: boolean
  signIn: (token: string, user: User) => void
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(!getToken())
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    if (!getToken()) return
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])

  useEffect(() => {
    const onExpired = () => { setUser(null); setExpired(true) }
    window.addEventListener(SESSION_EXPIRED, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED, onExpired)
  }, [])

  const signIn = useCallback((token: string, u: User) => { setToken(token); setUser(u); setExpired(false) }, [])
  const signOut = useCallback(() => { setToken(null); setUser(null); setExpired(false) }, [])

  return <AuthContext.Provider value={{ user, ready, expired, signIn, signOut }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

export function homeFor(user: User | null) {
  if (!user || user.role === 'buyer') return '/catalogue'
  return '/dashboard'
}
