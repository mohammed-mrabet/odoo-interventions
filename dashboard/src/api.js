// Accès à Odoo : authentification par session (cookie) puis appels à l'API JSON du module.

const DB = import.meta.env.VITE_ODOO_DB || ''

async function jsonRpc(url, params) {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params }),
  })
  const data = await response.json()
  if (data.error) throw new Error(data.error.data?.message || data.error.message)
  return data.result
}

export async function login(login, password, db = DB) {
  const result = await jsonRpc('/web/session/authenticate', { db, login, password })
  if (!result?.uid) throw new Error('Identifiants incorrects')
  return result
}

export async function currentSession() {
  try {
    const result = await jsonRpc('/web/session/get_session_info', {})
    return result?.uid ? result : null
  } catch {
    return null
  }
}

export function logout() {
  return jsonRpc('/web/session/destroy', {})
}

async function getJson(url) {
  const response = await fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } })
  if (response.redirected || response.status === 401 || response.status === 403) throw new Error('SESSION_EXPIRED')
  if (!response.ok) throw new Error(`Erreur ${response.status}`)
  return response.json()
}

export const fetchStats = () => getJson('/api/interventions/stats')
export const fetchInterventions = (state) => getJson(`/api/interventions?limit=100${state ? `&state=${state}` : ''}`)
