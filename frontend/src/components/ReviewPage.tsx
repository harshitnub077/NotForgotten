import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CheckCircle, ChevronRight, Trophy, ArrowLeft, Loader } from 'lucide-react';

/* ── Types ────────────────────────────────────── */
interface Card {
  concept_id: string;
  urgency_score: number;
  retention_prob: number;
  front: string;   // The question
  back: string;    // The answer
}

/* ── Mock cards ──────────────────────────────── */
const MOCK_CARDS: Card[] = [
  {
    concept_id: 'ChromaDB Search',
    urgency_score: 0.53,
    retention_prob: 0.47,
    front: 'How does ChromaDB perform vector similarity search?',
    back: 'ChromaDB converts the query into a vector embedding, then computes approximate nearest neighbor (ANN) distances — typically cosine similarity — against all stored vectors. It returns the top-k most similar document chunks, enabling semantic retrieval without exact keyword matching.',
  },
  {
    concept_id: 'FastAPI DI',
    urgency_score: 0.45,
    retention_prob: 0.55,
    front: 'What is FastAPI Dependency Injection and why use it?',
    back: 'FastAPI DI uses Python type hints and the `Depends()` function to declare shared dependencies like database connections, auth, or services. They are resolved automatically per request, promoting separation of concerns, testability, and avoiding duplicate setup code.',
  },
  {
    concept_id: 'SM-2 Algorithm',
    urgency_score: 0.39,
    retention_prob: 0.61,
    front: 'What does the SM-2 algorithm compute, and when is an item re-shown?',
    back: 'SM-2 computes: (1) Ease Factor (EF), adjusted by your recall quality (0-5). (2) Interval = previous interval × EF. (3) Next review date = today + interval. Items rated < 3 reset to interval=1 and repeat until mastered. EF stays ≥ 1.3.',
  },
  {
    concept_id: 'Ebbinghaus Curve',
    urgency_score: 0.22,
    retention_prob: 0.78,
    front: 'What is the Ebbinghaus Forgetting Curve formula?',
    back: 'Retention(t) = e^(−t/S), where t = time since learning and S = memory stability (a personal constant). Without review, retention drops to ~58% after 1 day, ~33% after 1 week, and ~21% after a month. Spaced repetition resets the curve at each review.',
  },
  {
    concept_id: 'Hybrid Retrieval',
    urgency_score: 0.18,
    retention_prob: 0.82,
    front: 'How does ForgetLess AI combine semantic similarity with memory urgency?',
    back: 'Final score = α × semantic_similarity + β × forgetting_probability + γ × low_retention_boost. The hybrid retriever first fetches top-3k semantic candidates from ChromaDB, then re-ranks them using the computed urgency scores from the SM-2 memory state, injecting high-forgetting-risk chunks even if less semantically relevant.',
  },
];

const RATING_CONFIG = [
  { score: 1, label: 'Again',   emoji: '😰', color: '#ef4444', hint: 'Complete blackout' },
  { score: 2, label: 'Hard',    emoji: '😓', color: '#f97316', hint: 'Recalled with effort' },
  { score: 3, label: 'Good',    emoji: '🙂', color: '#84cc16', hint: 'Recalled with pause' },
  { score: 4, label: 'Easy',    emoji: '😎', color: '#10b981', hint: 'Fast, correct recall' },
  { score: 5, label: 'Perfect', emoji: '🤩', color: '#6366f1', hint: 'Instant, perfect recall' },
];

/* ── Flip Card Component ─────────────────────── */
const FlipCard = ({ card, onFlip, flipped }: { card: Card; onFlip: () => void; flipped: boolean }) => (
  <div
    onClick={onFlip}
    style={{ perspective: 1200, cursor: 'pointer', width: '100%', maxWidth: 560, height: 300 }}
  >
    <motion.div
      animate={{ rotateY: flipped ? 180 : 0 }}
      transition={{ duration: 0.55, ease: [0.4, 0, 0.2, 1] }}
      style={{ width: '100%', height: '100%', position: 'relative', transformStyle: 'preserve-3d' }}
    >
      {/* Front */}
      <div style={{
        position: 'absolute', inset: 0,
        backfaceVisibility: 'hidden',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-3xl)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: 'var(--space-8)',
        textAlign: 'center',
      }}>
        <div style={{ marginBottom: 'var(--space-4)', opacity: 0.4 }}>
          <Brain size={28} color="var(--accent)" />
        </div>
        <p style={{ fontSize: '1.1rem', fontWeight: 600, lineHeight: 1.6, color: 'var(--text-primary)', maxWidth: 420 }}>
          {card.front}
        </p>
        <p style={{ marginTop: 'var(--space-5)', fontSize: '0.78rem', color: 'var(--text-dimmed)' }}>
          tap to reveal answer
        </p>
      </div>

      {/* Back */}
      <div style={{
        position: 'absolute', inset: 0,
        backfaceVisibility: 'hidden',
        transform: 'rotateY(180deg)',
        background: 'var(--bg-elevated)',
        border: '1px solid rgba(99,102,241,0.3)',
        borderRadius: 'var(--r-3xl)',
        display: 'flex', flexDirection: 'column',
        justifyContent: 'center',
        padding: 'var(--space-8)',
        boxShadow: '0 0 40px var(--accent-glow-lg)',
      }}>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 'var(--space-3)' }}>
          Answer
        </div>
        <p style={{ fontSize: '0.9rem', lineHeight: 1.75, color: 'var(--text-secondary)' }}>
          {card.back}
        </p>
      </div>
    </motion.div>
  </div>
);

/* ── Session Complete Screen ─────────────────── */
const SessionComplete = ({ total, onRestart }: { total: number; onRestart: () => void }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-16)', textAlign: 'center',
    }}
  >
    <motion.div
      animate={{ scale: [1, 1.1, 1] }}
      transition={{ duration: 0.6, delay: 0.2 }}
      style={{
        width: 80, height: 80, borderRadius: 'var(--r-full)',
        background: 'linear-gradient(135deg, var(--success), #059669)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 'var(--space-6)',
        boxShadow: '0 0 40px rgba(16,185,129,0.4)',
      }}
    >
      <Trophy size={36} color="white" />
    </motion.div>
    <h2 style={{ fontSize: '2rem', marginBottom: 'var(--space-3)' }}>Session Complete!</h2>
    <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginBottom: 'var(--space-8)' }}>
      You reviewed <strong>{total} concepts</strong>. The SM-2 algorithm has updated<br />
      your next review dates based on your performance.
    </p>
    <div style={{ display: 'flex', gap: 'var(--space-4)' }}>
      <button onClick={onRestart} className="btn-ghost">
        <RotateCcw size={14} /> Review Again
      </button>
    </div>
  </motion.div>
);

const RotateCcw = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
  </svg>
);

/* ── Review Page ─────────────────────────────── */
const ReviewPage = () => {
  const [cards, setCards]     = useState<Card[]>([]);
  const [cardIdx, setCardIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [rating, setRating]   = useState(false);
  const [done, setDone]       = useState(false);
  const [isMock, setIsMock]   = useState(false);
  const [sessionId]   = useState(() => crypto.randomUUID());
  const [reviewed, setReviewed] = useState<{ concept_id: string; score: number }[]>([]);

  const loadCards = async () => {
    setLoading(true); setDone(false); setCardIdx(0);
    setFlipped(false); setReviewed([]);
    try {
      const r = await axios.post('/session/start');
      const raw: { concept_id: string; urgency_score: number }[] = r.data.urgent_concepts?.slice(0, 6) ?? [];
      if (raw.length === 0) throw new Error('no concepts');
      // Build cards from urgent concepts (front = question, back = placeholder until AI generates)
      const built = raw.map(c => ({
        concept_id: c.concept_id, urgency_score: c.urgency_score,
        retention_prob: 1 - c.urgency_score,
        front: `Explain ${c.concept_id} — what are the key mechanisms and use cases?`,
        back: `This is the stored knowledge chunk for "${c.concept_id}". In a live session, the LLM generates a tailored explanation based on your vector store content.`,
      }));
      setCards(built);
    } catch {
      setCards(MOCK_CARDS);
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCards(); }, []);

  const handleRate = async (score: number) => {
    setRating(true);
    const card = cards[cardIdx];
    try {
      await axios.post('/session/rate', {
        session_id: sessionId,
        concept_id: card.concept_id,
        rating: score
      });
    } catch {}
    setReviewed(prev => [...prev, { concept_id: card.concept_id, score }]);

    if (cardIdx + 1 >= cards.length) {
      setDone(true);
    } else {
      setCardIdx(i => i + 1);
      setFlipped(false);
    }
    setRating(false);
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '80vh' }}>
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
        <Loader size={32} color="var(--accent)" />
      </motion.div>
    </div>
  );

  if (done) return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 'var(--space-8)' }}>
      <SessionComplete total={reviewed.length} onRestart={loadCards} />
      {/* Session summary */}
      <div className="card" style={{ padding: 'var(--space-5)', marginTop: 'var(--space-8)' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 'var(--space-4)' }}>Session Summary</h3>
        {reviewed.map(r => {
          const cfg = RATING_CONFIG.find(c => c.score === r.score) ?? RATING_CONFIG[2];
          return (
            <div key={r.concept_id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: 'var(--space-3) 0', borderBottom: '1px solid var(--border)',
            }}>
              <span style={{ fontSize: '0.875rem' }}>{r.concept_id}</span>
              <span style={{
                fontSize: '0.78rem', fontWeight: 600, padding: '2px 10px',
                borderRadius: 'var(--r-full)', background: `${cfg.color}22`, color: cfg.color,
              }}>
                {cfg.emoji} {cfg.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );

  const currentCard = cards[cardIdx];
  if (!currentCard) return null;

  const urgencyPct = Math.round(currentCard.urgency_score * 100);

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 'var(--space-8)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

      {/* Header */}
      <div style={{ width: '100%', marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <div>
            <h1 style={{ fontSize: '1.4rem', marginBottom: 4 }}>Flashcard Review</h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Reviewing by urgency — highest forgetting risk first
            </p>
          </div>
          {isMock && <span className="badge badge-warning" style={{ fontSize: '0.68rem' }}>Demo Mode</span>}
        </div>

        {/* Progress bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div style={{ flex: 1, height: 6, background: 'var(--bg-surface)', borderRadius: 3, overflow: 'hidden' }}>
            <motion.div
              animate={{ width: `${((cardIdx) / cards.length) * 100}%` }}
              style={{ height: '100%', background: 'linear-gradient(90deg, var(--accent), var(--violet-500))', borderRadius: 3 }}
              transition={{ duration: 0.4 }}
            />
          </div>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', flexShrink: 0 }}>{cardIdx + 1} / {cards.length}</span>
        </div>
      </div>

      {/* Concept badge + urgency */}
      <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-5)', alignItems: 'center' }}>
        <span className={`badge ${urgencyPct > 40 ? 'badge-danger' : urgencyPct > 20 ? 'badge-warning' : 'badge-success'}`}>
          <Brain size={10} /> {urgencyPct}% urgency
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{currentCard.concept_id}</span>
      </div>

      {/* Card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={cardIdx}
          initial={{ opacity: 0, x: 40, scale: 0.96 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: -40, scale: 0.96 }}
          transition={{ duration: 0.25 }}
          style={{ width: '100%', display: 'flex', justifyContent: 'center', marginBottom: 'var(--space-8)' }}
        >
          <FlipCard card={currentCard} flipped={flipped} onFlip={() => setFlipped(f => !f)} />
        </motion.div>
      </AnimatePresence>

      {/* Rating buttons — shown after flip */}
      <AnimatePresence>
        {flipped && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{ width: '100%' }}
          >
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: 'var(--space-4)' }}>
              How well did you recall this?
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-3)' }}>
              {RATING_CONFIG.map(r => (
                <motion.button
                  key={r.score}
                  whileHover={{ scale: 1.04, y: -2 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => handleRate(r.score)}
                  disabled={rating}
                  style={{
                    padding: 'var(--space-4) var(--space-3)',
                    background: 'var(--bg-elevated)',
                    border: `1px solid ${r.color}44`,
                    borderRadius: 'var(--r-xl)',
                    cursor: 'pointer', textAlign: 'center',
                    transition: 'background 0.2s',
                    opacity: rating ? 0.6 : 1,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = `${r.color}1a`)}
                  onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                >
                  <div style={{ fontSize: '1.4rem', marginBottom: 4 }}>{r.emoji}</div>
                  <div style={{ fontWeight: 700, color: r.color, fontSize: '0.875rem' }}>{r.label}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>{r.hint}</div>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!flipped && (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ color: 'var(--text-dimmed)', fontSize: '0.78rem', textAlign: 'center', marginTop: 'var(--space-4)' }}>
          Click the card to reveal the answer, then rate your recall.
        </motion.p>
      )}

    </div>
  );
};

export default ReviewPage;
