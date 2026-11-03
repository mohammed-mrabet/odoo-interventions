import { useCallback, useEffect, useState } from 'react'
import { currentSession, fetchInterventions, fetchStats, login, logout } from './api.js'
import Dashboard from './Dashboard.jsx'

export default function App() {
  const [session, setSession] = useState(undefined) // undefined = vérification en cours
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      setStats(await fetchStats())
    } catch (e) {
      if (e.message === 'SESSION_EXPIRED') setSession(null)
      else setError(e.message)
    }
  }, [])

  useEffect(() => {
    currentSession().then(setSession)
  }, [])

  useEffect(() => {
    if (!session) return
    load()
    const timer = setInterval(load, 60_000) // rafraîchissement automatique chaque minute
    return () => clearInterval(timer)
  }, [session, load])

  if (session === undefined) return <p className="center muted">Connexion…</p>
  if (!session) return <LoginForm onLogin={setSession} />

  return (
    <Dashboard
      stats={stats}
      error={error}
      userName={session.name}
      onRefresh={load}
      onLogout={async () => {
        await logout()
        setSession(null)
        setStats(null)
      }}
      fetchInterventions={fetchInterventions}
    />
  )
}

function LoginForm({ onLogin }) {
  const [form, setForm] = useState({ login: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onLogin(await login(form.login, form.password))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <form className="card login__card" onSubmit={submit}>
        <div className="brand"><span className="brand__logo">🔧</span> Interventions</div>
        <p className="muted">Connectez-vous avec votre compte Odoo.</p>
        <label>
          Identifiant
          <input autoFocus value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} required />
        </label>
        <label>
          Mot de passe
          <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn btn--primary" disabled={busy}>{busy ? 'Connexion…' : 'Se connecter'}</button>
      </form>
    </div>
  )
}
