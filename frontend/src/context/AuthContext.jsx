import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.get()))

  const loadMe = useCallback(async () => {
    try {
      setUser(await api.get('/auth/me'))
    } catch {
      tokenStore.clear()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tokenStore.get()) loadMe()
    const onExpired = () => setUser(null)
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [loadMe])

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password })
    tokenStore.set(res.access_token)
    const me = await api.get('/auth/me')
    setUser(me)
    return me
  }

  const logout = () => {
    tokenStore.clear()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
