import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { getCurrentUser, login as loginRequest } from '../api/auth'
import { TOKEN_KEY } from '../api/client'
import type { User } from '../types/api'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }, [])

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setIsLoading(false)
      return
    }

    getCurrentUser()
      .then(setUser)
      .catch(logout)
      .finally(() => setIsLoading(false))
  }, [logout])

  useEffect(() => {
    window.addEventListener('blue-music:auth-failed', logout)
    return () => window.removeEventListener('blue-music:auth-failed', logout)
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    const token = await loginRequest(username, password)
    localStorage.setItem(TOKEN_KEY, token.access_token)
    try {
      setUser(await getCurrentUser())
    } catch (error) {
      localStorage.removeItem(TOKEN_KEY)
      throw error
    }
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
