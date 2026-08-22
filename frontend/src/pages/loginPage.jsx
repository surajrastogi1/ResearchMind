import { useState } from 'react'
import AuthShell from '../components/AuthShell.jsx'
import { API_URL } from '../api.js'

const LoginPage = ({ onNavigate }) => {
  const [form, setForm] = useState({ username: '', password: '' })
  const [status, setStatus] = useState({ type: '', message: '' })
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleChange = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus({ type: '', message: '' })
    setIsSubmitting(true)

    try {
      const body = new URLSearchParams(form)
      const response = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      const data = await response.json()

      if (!response.ok) throw new Error(data.detail || 'Unable to sign in.')

      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('username', data.username)
      onNavigate('/home')
    } catch (error) {
      setStatus({ type: 'error', message: error.message })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="PDF Research Assistant"
      title="Welcome back."
      description="Pick up your research exactly where you left it."
      footer={<>New here? <button type="button" onClick={() => onNavigate('/register')}>Create an account</button></>}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="login-username">Username</label>
          <input id="login-username" name="username" value={form.username} onChange={handleChange} placeholder="your username" autoComplete="username" required />
        </div>
        <div className="field-group">
          <label htmlFor="login-password">Password</label>
          <input id="login-password" name="password" type="password" value={form.password} onChange={handleChange} placeholder="Enter your password" autoComplete="current-password" required />
        </div>
        {status.message && <p className={`form-message ${status.type}`} role="alert">{status.message}</p>}
        <button className="submit-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </AuthShell>
  )
}

export default LoginPage
