import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Search, ChevronRight, BookOpen, Zap, RotateCcw, CheckCircle } from 'lucide-react';

/* ── Types ────────────────────────────────────── */
interface UrgentConcept { concept_id: string; urgency_score: number; }
interface Source { concept_tag: string; source_file: string; }
interface QueryResponse { answer: string; sources: Source[]; }

type Step = 'SELECT' | 'LOADING' | 'ANSWER' | 'RATE';

/* ── Mock data ───────────────────────────────── */
const MOCK_CONCEPTS: UrgentConcept[] = [
  { concept_id: 'LangGraph State Machine', urgency_score: 0.95 },
  { concept_id: 'Ebbinghaus Forgetting Curve', urgency_score: 0.88 },
  { concept_id: 'ChromaDB Vector Search', urgency_score: 0.80 },
  { concept_id: 'FastAPI Dependency Injection', urgency_score: 0.72 },
  { concept_id: 'SM-2 Spaced Repetition', urgency_score: 0.65 },
];

const MOCK_ANSWER = (concept: string) => ({
  answer: `The core mechanism of **${concept}** involves maintaining state across computation nodes in a directed graph. Each node can read and write to a shared state object, enabling complex workflows like multi-hop retrieval, conditional branching, and iterative refinement without losing context between steps.`,
  sources: [
    { concept_tag: concept, source_file: 'lecture_notes.pdf' },
    { concept_tag: concept, source_file: 'textbook_ch3.pdf' },
  ],
});

/* ── Rating Button ───────────────────────────── */
const RatingButton = ({
  score, label, color, onClick,
}: { score: number; label: string; color: string; onClick: () => void }) => (
  <motion.button
    whileHover={{ scale: 1.04, boxShadow: `0 0 24px ${color}44` }}
    whileTap={{ scale: 0.97 }}
    onClick={onClick}
    style={{
      padding: 'var(--space-5) var(--space-4)',
      background: 'var(--bg-elevated)',
      border: `1px solid ${color}33`,
      borderRadius: 'var(--r-xl)',
      color: 'white',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-2)',
      cursor: 'pointer', transition: 'background 0.2s',
      flex: 1,
    }}
    onMouseEnter={e => (e.currentTarget.style.background = `${color}22`)}
    onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
  >
    <span style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'var(--font-display)', color }}>{score}</span>
    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center' }}>{label}</span>
  </motion.button>
);

/* ── Session Interface ───────────────────────── */
const SessionInterface = () => {
  const [concepts, setConcepts]   = useState<UrgentConcept[]>([]);
  const [active, setActive]       = useState('');
  const [query, setQuery]         = useState('');
  const [response, setResponse]   = useState<QueryResponse | null>(null);
  const [step, setStep]           = useState<Step>('SELECT');
  const [sessionCount, setSessionCount] = useState(0);
  const [isMock, setIsMock]       = useState(false);

  /* Load urgent concepts */
  useEffect(() => {
    axios.post('/session/start')
      .then(res => {
        setConcepts(res.data.urgent_concepts?.slice(0, 5) ?? MOCK_CONCEPTS);
        setIsMock(false);
      })
      .catch(() => { setConcepts(MOCK_CONCEPTS); setIsMock(true); });
  }, []);

  /* Pick a concept card */
  const pickConcept = (concept: UrgentConcept) => {
    setActive(concept.concept_id);
    setQuery(`Explain ${concept.concept_id}`);
    submitQuery(`Explain ${concept.concept_id}`, concept.concept_id);
  };

  /* Submit query to the AI */
  const submitQuery = async (q: string, conceptId: string) => {
    setStep('LOADING');
    setResponse(null);
    try {
      const res = await axios.post('/session/query', { query: q, concept_id: conceptId });
      setResponse(res.data);
    } catch {
      await new Promise(r => setTimeout(r, 1400));
      setResponse(MOCK_ANSWER(conceptId || q));
    }
    setStep('ANSWER');
  };

  const handleFreeQuery = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setActive('');
    submitQuery(query, query);
  };

  /* Rate memory */
  const handleRate = async (score: number) => {
    const conceptToRate = active || response?.sources?.[0]?.concept_tag || 'general';
    try {
      await axios.post('/session/rate', { concept_id: conceptToRate, rating: score });
    } catch {}
    setSessionCount(c => c + 1);
    setResponse(null);
    setQuery('');
    setActive('');
    setStep('SELECT');
  };

  const ratings = [
    { score: 0, label: 'Blackout',  color: '#ef4444' },
    { score: 1, label: 'Barely',    color: '#f97316' },
    { score: 2, label: 'Struggled', color: '#eab308' },
    { score: 3, label: 'Good',      color: '#84cc16' },
    { score: 4, label: 'Perfect',   color: '#10b981' },
  ];

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto', padding: 'var(--space-10) var(--space-6)', minHeight: 'calc(100vh - 60px)' }}>

      {/* Header */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ fontSize: 'clamp(1.6rem, 3vw, 2.2rem)', marginBottom: 'var(--space-2)' }}>
              Learning Session
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Review concepts at risk of being forgotten. Rate your recall to update the algorithm.
            </p>
          </div>
          {sessionCount > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <CheckCircle size={16} color="var(--success)" />
              <span style={{ color: 'var(--success)', fontSize: '0.875rem', fontWeight: 600 }}>
                {sessionCount} reviewed
              </span>
            </div>
          )}
        </div>
        {isMock && (
          <span className="badge badge-warning" style={{ marginTop: 'var(--space-3)', display: 'inline-flex' }}>
            Mock mode — start the FastAPI backend for real AI responses
          </span>
        )}
      </div>

      <AnimatePresence mode="wait">

        {/* ── SELECT STEP ────────────────────────── */}
        {step === 'SELECT' && (
          <motion.div
            key="select"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
          >
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-5)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <Brain size={18} color="var(--danger)" /> High-Urgency Concepts
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-8)' }}>
              {concepts.map((c, i) => {
                const pct = Math.round(c.urgency_score * 100);
                const color = pct > 85 ? 'var(--danger)' : pct > 70 ? 'var(--warning)' : 'var(--success)';
                return (
                  <motion.button
                    key={c.concept_id}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.06 }}
                    whileHover={{ x: 4 }}
                    onClick={() => pickConcept(c)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: 'var(--space-5)',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r-xl)',
                      color: 'var(--text-primary)',
                      width: '100%', textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'border-color var(--ease-fast), box-shadow var(--ease-fast)',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'var(--border-hover)';
                      e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: 'var(--r-lg)',
                        background: `${color.replace('var(', '').replace(')', '')}22`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        border: `1px solid ${pct > 85 ? 'rgba(239,68,68,0.3)' : pct > 70 ? 'rgba(245,158,11,0.3)' : 'rgba(16,185,129,0.3)'}`,
                      }}>
                        <Brain size={16} color={color} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{c.concept_id}</div>
                        <div style={{ color, fontSize: '0.78rem', marginTop: 2, fontWeight: 500 }}>
                          {pct}% urgency — Review now
                        </div>
                      </div>
                    </div>
                    <ChevronRight size={18} color="var(--text-muted)" />
                  </motion.button>
                );
              })}
            </div>

            {/* Free-form query */}
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 'var(--space-8)' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <Search size={16} /> Ask Anything
              </h2>
              <form onSubmit={handleFreeQuery} style={{ display: 'flex', gap: 'var(--space-3)' }}>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. How does ChromaDB handle similarity search?"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button type="submit" className="btn-primary" disabled={!query.trim()}>
                  <Zap size={15} /> Ask
                </button>
              </form>
            </div>
          </motion.div>
        )}

        {/* ── LOADING STEP ───────────────────────── */}
        {step === 'LOADING' && (
          <motion.div
            key="loading"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-24)' }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
              style={{ marginBottom: 'var(--space-5)' }}
            >
              <Brain size={48} color="var(--accent)" />
            </motion.div>
            <h3 style={{ fontSize: '1.1rem', marginBottom: 'var(--space-2)' }}>Retrieving from knowledge graph…</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Searching semantic embeddings and generating a grounded response.
            </p>

            {/* Animated loading steps */}
            <div style={{ marginTop: 'var(--space-8)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', width: '100%', maxWidth: 360 }}>
              {['Scanning ChromaDB vector index', 'Re-ranking top-k passages', 'Synthesizing answer via LLM'].map((t, i) => (
                <motion.div
                  key={t}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.4 }}
                  style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', color: 'var(--text-muted)', fontSize: '0.82rem' }}
                >
                  <motion.div
                    animate={{ scale: [1, 1.3, 1] }}
                    transition={{ repeat: Infinity, duration: 1.2, delay: i * 0.2 }}
                    style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }}
                  />
                  {t}
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── ANSWER STEP ────────────────────────── */}
        {step === 'ANSWER' && response && (
          <motion.div
            key="answer"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            {/* Query chip */}
            <div style={{
              padding: 'var(--space-4) var(--space-5)',
              background: 'var(--indigo-900)',
              border: '1px solid rgba(99,102,241,0.2)',
              borderRadius: 'var(--r-xl)',
              marginBottom: 'var(--space-5)',
              display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)',
            }}>
              <span style={{ color: 'var(--indigo-400)', fontWeight: 700, fontSize: '0.85rem', flexShrink: 0 }}>Q:</span>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>{query}</span>
            </div>

            {/* Answer */}
            <div className="card" style={{ padding: 'var(--space-6)', marginBottom: 'var(--space-5)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                <Zap size={16} color="var(--accent)" />
                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--accent)' }}>AI Response</span>
              </div>
              <p style={{ color: 'var(--text-primary)', lineHeight: 1.85, fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
                {response.answer.replace(/\*\*/g, '')}
              </p>
              <div style={{
                marginTop: 'var(--space-5)',
                paddingTop: 'var(--space-4)',
                borderTop: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                color: 'var(--text-muted)', fontSize: '0.8rem',
              }}>
                <BookOpen size={13} />
                Sources: {response.sources.map(s => s.source_file).join(', ')}
              </div>
            </div>

            {/* Action row */}
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <button
                onClick={() => setStep('RATE')}
                className="btn-primary"
                style={{ flex: 1, justifyContent: 'center' }}
              >
                <Brain size={15} /> Rate My Recall
              </button>
              <button
                onClick={() => { setStep('SELECT'); setResponse(null); setQuery(''); setActive(''); }}
                className="btn-ghost"
              >
                <RotateCcw size={14} /> Skip
              </button>
            </div>
          </motion.div>
        )}

        {/* ── RATE STEP ──────────────────────────── */}
        {step === 'RATE' && (
          <motion.div
            key="rate"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <div className="card" style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
              <div style={{
                width: 56, height: 56, borderRadius: 'var(--r-full)',
                background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto var(--space-5)',
                boxShadow: '0 0 24px var(--accent-glow)',
              }}>
                <Brain size={24} color="white" />
              </div>
              <h2 style={{ fontSize: '1.4rem', marginBottom: 'var(--space-3)' }}>Rate Your Recall</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: 420, margin: '0 auto var(--space-8)' }}>
                Your honest rating updates the SM-2 algorithm and schedules the next review at the optimal moment.
              </p>

              <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center' }}>
                {ratings.map(r => (
                  <RatingButton key={r.score} {...r} onClick={() => handleRate(r.score)} />
                ))}
              </div>

              <div style={{
                marginTop: 'var(--space-6)',
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 'var(--space-2)',
                paddingTop: 'var(--space-4)',
                borderTop: '1px solid var(--border)',
              }}>
                {['Complete blackout', 'Remembered with struggle', 'Recalled with effort', 'Good response', 'Perfect recall'].map((tip, i) => (
                  <div key={i} style={{ color: 'var(--text-dimmed)', fontSize: '0.7rem', lineHeight: 1.4 }}>{tip}</div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
};

export default SessionInterface;
