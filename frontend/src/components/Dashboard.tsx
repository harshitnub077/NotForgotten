import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts';
import { Brain, Activity, Clock, TrendingUp, Zap, ArrowRight, RefreshCw, AlertTriangle, Database } from 'lucide-react';

/* ── Mock data (Empty) ───────────────────────── */
const MOCK_CONCEPTS: any[] = [];

const MOCK_STATS = {
  total_concepts: 0, avg_retention_prob: 0,
  total_sessions: 0, avg_interval_days: 0,
};

// Forgetting curve data (with vs without review)
const CURVE_DATA = [
  { day: 'D0', noReview: 1.0, withReview: 1.0 },
  { day: 'D1', noReview: 0.58, withReview: 0.88 },
  { day: 'D3', noReview: 0.44, withReview: 0.79 },
  { day: 'D7', noReview: 0.33, withReview: 0.87 },
  { day: 'D14', noReview: 0.24, withReview: 0.92 },
  { day: 'D21', noReview: 0.18, withReview: 0.90 },
  { day: 'D30', noReview: 0.14, withReview: 0.88 },
];

/* ── Helpers ─────────────────────────────────── */
const retColor = (r: number) =>
  r >= 0.8 ? 'var(--success)' : r >= 0.55 ? 'var(--warning)' : 'var(--danger)';

/* ── Stat Card ───────────────────────────────── */
const Stat = ({ label, value, sub, gradient, icon }: {
  label: string; value: string | number; sub?: string;
  gradient: string; icon: React.ReactNode;
}) => (
  <motion.div className="card" whileHover={{ y: -2 }} style={{ padding: 'var(--space-5)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-4)' }}>
      <div style={{ width: 38, height: 38, borderRadius: 'var(--r-lg)', background: gradient, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </div>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
    </div>
    <div style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.04em' }}>{value}</div>
    {sub && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
  </motion.div>
);

/* ── Custom Tooltip ──────────────────────────── */
const CTip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', padding: '10px 14px' }}>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 4 }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color, fontWeight: 600, fontSize: '0.875rem' }}>
          {p.name}: {(p.value * 100).toFixed(0)}%
        </p>
      ))}
    </div>
  );
};

/* ── Dashboard ───────────────────────────────── */
const Dashboard = () => {
  const [concepts, setConcepts] = useState(MOCK_CONCEPTS);
  const [stats, setStats] = useState(MOCK_STATS);
  const [loading, setLoading] = useState(true);
  const [isMock, setIsMock] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const r = await axios.get('/dashboard');
      if (r.data?.memory?.length) setConcepts(r.data.memory);
      if (r.data?.stats) setStats(r.data.stats);
      setIsMock(false);
    } catch {
      setIsMock(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  const dueToday = concepts.filter(c => c.urgency_score > 0.35 || c.next_review === 'Today');
  const weakConcepts = [...concepts].sort((a, b) => a.retention_prob - b.retention_prob).slice(0, 5);

  const barData = concepts.map(c => ({
    name: c.concept_id.length > 12 ? c.concept_id.slice(0, 12) + '…' : c.concept_id,
    value: Math.round(c.retention_prob * 100),
  }));

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
        <Brain size={40} color="var(--accent)" />
      </motion.div>
    </div>
  );

  return (
    <div style={{ padding: 'var(--space-8)', maxWidth: 1140, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-8)' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', marginBottom: 6 }}>Memory Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Track forgetting curves, retention health, and upcoming reviews.
          </p>
          {isMock && (
            <span className="badge badge-warning" style={{ marginTop: 8, display: 'inline-flex' }}>
              <AlertTriangle size={10} /> Demo data — backend offline
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button onClick={() => { setRefreshing(true); load(); }} className="btn-ghost" style={{ padding: '8px 14px', fontSize: '0.8rem' }}>
            <motion.div animate={{ rotate: refreshing ? 360 : 0 }} transition={{ duration: 0.8, repeat: refreshing ? Infinity : 0 }}>
              <RefreshCw size={13} />
            </motion.div>
            Refresh
          </button>
          <Link to="/review" className="btn-primary" style={{ padding: '8px 16px', fontSize: '0.875rem' }}>
            <Zap size={13} /> Start Review
          </Link>
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
        <Stat label="Concepts Tracked" value={stats.total_concepts} sub="across all documents"
          gradient="linear-gradient(135deg,#6366f1,#8b5cf6)" icon={<Database size={16} color="white" />} />
        <Stat label="Avg Retention" value={`${Math.round((stats.avg_retention_prob) * 100)}%`} sub="memory strength"
          gradient="linear-gradient(135deg,#10b981,#059669)" icon={<Activity size={16} color="white" />} />
        <Stat label="Sessions" value={stats.total_sessions} sub="total learning sessions"
          gradient="linear-gradient(135deg,#f59e0b,#f97316)" icon={<Clock size={16} color="white" />} />
        <Stat label="Due Today" value={dueToday.length} sub="concepts need review"
          gradient="linear-gradient(135deg,#ef4444,#dc2626)" icon={<AlertTriangle size={16} color="white" />} />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 'var(--space-5)', marginBottom: 'var(--space-5)' }}>

        {/* Forgetting Curve Comparison */}
        <div className="card" style={{ padding: 'var(--space-5)' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 4 }}>Forgetting Curve Comparison</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: 'var(--space-4)' }}>
            Memory decay with vs without spaced repetition
          </p>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={CURVE_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="day" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} tickFormatter={v => `${Math.round(v * 100)}%`} />
                <Tooltip content={<CTip />} />
                <Line type="monotone" dataKey="noReview" name="No Review" stroke="var(--danger)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                <Line type="monotone" dataKey="withReview" name="With Reviews" stroke="var(--success)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-5)', marginTop: 'var(--space-3)' }}>
            {[{ color: 'var(--success)', label: 'With spaced review' }, { color: 'var(--danger)', label: 'No review', dash: true }].map(l => (
              <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <div style={{ width: 20, height: 2, background: l.color, borderRadius: 1, ...(l.dash ? { backgroundImage: 'repeating-linear-gradient(90deg,currentColor 0,currentColor 4px,transparent 4px,transparent 8px)', background: 'none', borderTop: `2px dashed ${l.color}` } : {}) }} />
                {l.label}
              </div>
            ))}
          </div>
        </div>

        {/* Retention by Concept */}
        <div className="card" style={{ padding: 'var(--space-5)' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 4 }}>Concept Retention</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: 'var(--space-4)' }}>
            Memory strength per concept (%)
          </p>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} width={90} />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Retention']} contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill={entry.value >= 80 ? '#10b981' : entry.value >= 55 ? '#f59e0b' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Bottom row: upcoming reviews + concept table */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 'var(--space-5)' }}>

        {/* Upcoming Reviews */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 700 }}>Upcoming Reviews</h3>
            <Link to="/review" style={{ fontSize: '0.75rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 4 }}>
              Review all <ArrowRight size={12} />
            </Link>
          </div>
          {dueToday.slice(0, 6).map((c, i) => (
            <motion.div
              key={c.concept_id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              style={{
                padding: 'var(--space-3) var(--space-5)',
                borderBottom: i < 5 ? '1px solid var(--border)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{c.concept_id}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: 2 }}>
                  {c.next_review}
                </div>
              </div>
              <span className={`badge ${c.retention_prob < 0.55 ? 'badge-danger' : c.retention_prob < 0.8 ? 'badge-warning' : 'badge-success'}`} style={{ fontSize: '0.7rem' }}>
                {Math.round(c.retention_prob * 100)}%
              </span>
            </motion.div>
          ))}
          {dueToday.length === 0 && (
            <div style={{ padding: 'var(--space-8)', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <TrendingUp size={24} style={{ margin: '0 auto 8px' }} color="var(--success)" />
              All caught up!
            </div>
          )}
        </div>

        {/* Concept Memory State */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 70px 80px 90px', gap: 'var(--space-3)' }}>
              {['Concept', 'Retention', 'Interval', 'Next Review'].map(h => (
                <div key={h} style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</div>
              ))}
            </div>
          </div>
          {weakConcepts.map((c, i) => (
            <div key={c.concept_id} style={{
              display: 'grid', gridTemplateColumns: '1fr 70px 80px 90px',
              gap: 'var(--space-3)', padding: 'var(--space-3) var(--space-5)',
              borderBottom: i < 4 ? '1px solid var(--border)' : 'none',
              alignItems: 'center',
            }}>
              <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{c.concept_id}</div>
              <div>
                <span style={{ fontWeight: 700, fontSize: '0.875rem', color: retColor(c.retention_prob) }}>
                  {Math.round(c.retention_prob * 100)}%
                </span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{c.interval_days}d</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{c.next_review}</div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
};

export default Dashboard;
