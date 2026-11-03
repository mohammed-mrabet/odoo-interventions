import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const STATES = [
  { key: 'draft', label: 'À planifier', color: '#94a3b8' },
  { key: 'planned', label: 'Planifiées', color: '#2563eb' },
  { key: 'in_progress', label: 'En cours', color: '#f59e0b' },
  { key: 'done', label: 'Terminées', color: '#16a34a' },
]
const TYPE_COLORS = ['#2563eb', '#16a34a', '#f59e0b', '#9333ea', '#dc2626']

const money = (value, currency) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: currency || 'MAD', maximumFractionDigits: 0 }).format(value || 0)

const dateTime = (value) =>
  value
    ? new Date(value.replace(' ', 'T') + 'Z').toLocaleString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '—'

export default function Dashboard({ stats, error, userName, onRefresh, onLogout, fetchInterventions }) {
  const [filter, setFilter] = useState('planned')
  const [list, setList] = useState([])

  useEffect(() => {
    fetchInterventions(filter).then((data) => setList(data.items)).catch(() => setList([]))
  }, [filter, stats, fetchInterventions])

  if (!stats) return <p className="center muted">{error || 'Chargement…'}</p>

  const s = stats.by_state
  return (
    <div className="page">
      <header className="topbar">
        <div className="brand"><span className="brand__logo">🔧</span> Tableau de bord des interventions</div>
        <div className="topbar__right">
          <span className="muted">{userName}</span>
          <button className="btn" onClick={onRefresh}>↻ Actualiser</button>
          <button className="btn btn--ghost" onClick={onLogout}>Déconnexion</button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="kpis">
        {STATES.map((st) => (
          <button key={st.key} className={`kpi ${filter === st.key ? 'kpi--active' : ''}`} style={{ borderTopColor: st.color }}
                  onClick={() => setFilter(st.key)}>
            <span className="kpi__label">{st.label}</span>
            <strong className="kpi__value">{s[st.key]}</strong>
          </button>
        ))}
        <div className="kpi kpi--danger">
          <span className="kpi__label">En retard</span>
          <strong className="kpi__value">{stats.late_count}</strong>
        </div>
        <div className="kpi kpi--wide">
          <span className="kpi__label">Chiffre d'affaires (30 j)</span>
          <strong className="kpi__value">{money(stats.revenue_30d, stats.currency)}</strong>
          <span className="kpi__hint">Durée moyenne : {stats.avg_duration_hours.toLocaleString('fr-FR')} h</span>
        </div>
      </section>

      <section className="grid">
        <div className="card">
          <h2>Charge par technicien</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stats.by_technician} margin={{ left: -20 }} maxBarSize={56}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey="open" name="À réaliser" stackId="a" fill="#2563eb" isAnimationActive={false} />
              <Bar dataKey="done" name="Terminées" stackId="a" fill="#16a34a" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h2>Répartition par type</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={stats.by_type} dataKey="count" nameKey="label" innerRadius={55} outerRadius={90} paddingAngle={2}>
                {stats.by_type.map((t, i) => <Cell key={t.type} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid">
        <InterventionTable title="⚠️ En retard" items={stats.late} empty="Aucune intervention en retard." currency={stats.currency} />
        <InterventionTable title="📅 7 prochains jours" items={stats.upcoming} empty="Rien de planifié cette semaine." currency={stats.currency} />
      </section>

      <InterventionTable
        title={`Interventions : ${STATES.find((st) => st.key === filter)?.label.toLowerCase()}`}
        items={list}
        empty="Aucune intervention."
        currency={stats.currency}
        full
      />
      <p className="muted small">Mis à jour : {dateTime(stats.generated_at)} · actualisation automatique chaque minute</p>
    </div>
  )
}

function InterventionTable({ title, items, empty, currency, full }) {
  return (
    <div className={`card card--flush ${full ? 'card--full' : ''}`}>
      <h2 className="card__title">{title}</h2>
      <table className="table">
        <thead>
          <tr><th>Référence</th><th>Client</th><th>Technicien</th><th>Date prévue</th>{full && <th>Type</th>}<th className="num">Montant</th></tr>
        </thead>
        <tbody>
          {items.length === 0 && <tr><td colSpan={full ? 6 : 5} className="muted empty">{empty}</td></tr>}
          {items.map((i) => (
            <tr key={i.id}>
              <td>
                <strong>{i.reference}</strong>
                {i.priority >= 2 && <span className="badge badge--danger">{i.priority === 3 ? 'Critique' : 'Urgent'}</span>}
              </td>
              <td>{i.client}</td>
              <td>{i.technician || <span className="warning">À affecter</span>}</td>
              <td className={i.is_late ? 'late' : ''}>{dateTime(i.date_planned)}</td>
              {full && <td>{i.type_label}</td>}
              <td className="num">{money(i.amount_total, currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
