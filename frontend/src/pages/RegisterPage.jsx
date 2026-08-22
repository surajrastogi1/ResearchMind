import { useState } from 'react'
import AuthShell from '../components/AuthShell.jsx'
import { API_URL } from '../api.js'

const RegisterPage = ({ onNavigate }) => {
  const [form, setForm] = useState({ username: '', email: '', password: '' })
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
      const response = await fetch(`${API_URL}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await response.json()

      if (!response.ok) throw new Error(data.detail || 'Unable to create your account.')
      const loginResponse = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: form.username, password: form.password }),
      })
      const loginData = await loginResponse.json()
      if (!loginResponse.ok) throw new Error(loginData.detail || 'Account created, but sign in failed.')
      localStorage.setItem('access_token', loginData.access_token)
      localStorage.setItem('username', loginData.username)
      onNavigate('/home')
    } catch (error) {
      setStatus({ type: 'error', message: error.message })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Start your workspace"
      title="Make research feel lighter."
      description="Organize your PDF work in one calm, focused place."
      footer={<>Already have an account? <button type="button" onClick={() => onNavigate('/login')}>Sign in</button></>}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="register-username">Username</label>
          <input id="register-username" name="username" value={form.username} onChange={handleChange} placeholder="Choose a username" autoComplete="username" required />
        </div>
        <div className="field-group">
          <label htmlFor="register-email">Email address</label>
          <input id="register-email" name="email" type="email" value={form.email} onChange={handleChange} placeholder="you@example.com" autoComplete="email" required />
        </div>
        <div className="field-group">
          <label htmlFor="register-password">Password</label>
          <input id="register-password" name="password" type="password" value={form.password} onChange={handleChange} placeholder="Create a password" autoComplete="new-password" required />
        </div>
        {status.message && <p className={`form-message ${status.type}`} role="alert">{status.message}</p>}
        <button className="submit-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}

export default RegisterPage
