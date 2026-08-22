import { useEffect, useState } from 'react'
import LoginPage from './pages/loginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import HomePage from './pages/HomePage.jsx'
import { API_URL } from './api.js'

const App = () => {
  const [path, setPath] = useState(window.location.pathname)
  const [isCheckingAuth, setIsCheckingAuth] = useState(window.location.pathname === '/home')

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (path !== '/home') return

    const token = localStorage.getItem('access_token')
    if (!token) {
      queueMicrotask(() => {
        setIsCheckingAuth(false)
        setPath('/login')
      })
      return
    }

    fetch(`${API_URL}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => {
      if (!response.ok) throw new Error('Session expired')
      return response.json()
    }).then((user) => {
      localStorage.setItem('username', user.username)
      setIsCheckingAuth(false)
    }).catch(() => {
      localStorage.removeItem('access_token')
      localStorage.removeItem('username')
      setIsCheckingAuth(false)
      setPath('/login')
    })
  }, [path])

  const navigate = (nextPath) => {
    window.history.pushState({}, '', nextPath)
    setPath(nextPath)
  }

  if (isCheckingAuth) return <div className="page-loading">Checking your workspace...</div>
  if (path === '/home') return <HomePage onNavigate={navigate} />
  if (path === '/login') return <LoginPage onNavigate={navigate} />
  return (
    <RegisterPage onNavigate={navigate} />
  )
}

export default App
