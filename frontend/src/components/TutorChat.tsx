import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Brain, Zap, AlertTriangle, BookOpen,
  RotateCcw, Sparkles, ChevronRight,
} from 'lucide-react';

/* ── Types ────────────────────────────────────── */
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  boosted?: string[];    // concepts that were memory-boosted
  timestamp: Date;
}

interface ConceptState {
  concept_id: string;
  retention_prob: number;
  urgency_score: number;
  next_review: string;
}

/* ── Mock data ───────────────────────────────── */
const MOCK_CONCEPTS: ConceptState[] = [
  { concept_id: 'ChromaDB Search',   retention_prob: 0.47, urgency_score: 0.53, next_review: 'Today'     },
  { concept_id: 'FastAPI DI',        retention_prob: 0.55, urgency_score: 0.45, next_review: 'Today'     },
  { concept_id: 'Vector Embeddings', retention_prob: 0.61, urgency_score: 0.39, next_review: 'Tomorrow'  },
  { concept_id: 'Ebbinghaus Curve',  retention_prob: 0.78, urgency_score: 0.22, next_review: 'In 2 days' },
  { concept_id: 'LangGraph',         retention_prob: 0.92, urgency_score: 0.08, next_review: 'In 5 days' },
];

const QUICK_PROMPTS = [
  { label: '🔁 Revise weak topics',      text: 'Revise my weakest topics with me. Start with the one I\'m most likely to forget.' },
  { label: '🧪 Test me',                 text: 'Test my knowledge with 3 questions on the concepts I\'ve studied.' },
  { label: '🤔 What am I forgetting?',   text: 'What concepts am I most at risk of forgetting right now?' },
  { label: '📚 Explain SM-2',            text: 'Explain how the SM-2 spaced repetition algorithm works.' },
];

const MOCK_RESPONSES = [
  (q: string) => ({
    reply: `Great question about **${q.slice(0, 30)}...**\n\n Based on your memory state, I can see that **ChromaDB Search** and **FastAPI Dependency Injection** are at risk of being forgotten — you haven't reviewed them in 4+ days and their retention is below 60%.\n\nLet me explain the key concept clearly:\n\nThe Ebbinghaus forgetting curve shows that without review, memory decays exponentially. The SM-2 algorithm fights this by scheduling reviews at *optimal* intervals — right before you would forget.\n\n> **You might be forgetting:** *Vector Embeddings* — last reviewed 6 days ago, retention at 61%.\n\nWould you like me to quiz you on this?`,
    boosted: ['ChromaDB Search', 'FastAPI DI'],
  }),
  (q: string) => ({
    reply: `I noticed your retention on **ChromaDB Search** (47%) is critically low. Let me reinforce it:\n\n**ChromaDB** uses approximate nearest neighbor (ANN) search on vector embeddings. When you query it, it:\n1. Converts your query to a vector via an embedding model\n2. Computes cosine similarity against stored vectors\n3. Returns the top-k closest chunks\n\nIn our system, this feeds directly into the hybrid retrieval scorer:\n\`final_score = α × semantic_score + (1−α) × urgency_score\`\n\n> ⚠️ **Memory Alert**: You're at risk of forgetting this concept within 2 days.`,
    boosted: ['ChromaDB Search'],
  }),
];

let mockIdx = 0;

/* ── Markdown-ish renderer ───────────────────── */
const renderMessage = (text: string) => {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    if (line.startsWith('> ')) return (
      <div key={i} style={{ borderLeft: '3px solid var(--accent)', paddingLeft: 12, margin: '8px 0', color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.875rem' }}>
        {line.slice(2)}
      </div>
    );
    if (line.startsWith('**') && line.endsWith('**')) return (
      <strong key={i} style={{ display: 'block', margin: '6px 0' }}>{line.slice(2, -2)}</strong>
    );
    if (/^\d+\./.test(line)) return (
      <div key={i} style={{ paddingLeft: 16, margin: '3px 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{line}</div>
    );
    if (line.includes('`') && line.split('`').length >= 3) {
      const parts = line.split('`');
      return (
        <p key={i} style={{ margin: '4px 0', fontSize: '0.9rem', lineHeight: 1.7 }}>
          {parts.map((p, j) => j % 2 === 1
            ? <code key={j} style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--indigo-300)', padding: '1px 6px', borderRadius: 4, fontFamily: 'var(--font-mono)', fontSize: '0.82em' }}>{p}</code>
            : <React.Fragment key={j}>{p.replace(/\*\*(.*?)\*\*/g, '$1')}</React.Fragment>
          )}
        </p>
      );
    }
    if (!line.trim()) return <div key={i} style={{ height: 8 }} />;
    return <p key={i} style={{ margin: '4px 0', lineHeight: 1.7, fontSize: '0.9rem' }}>{line.replace(/\*\*(.*?)\*\*/g, '$1')}</p>;
  });
};

/* ── Tutor Chat ───────────────────────────────── */
const TutorChat = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0', role: 'assistant', timestamp: new Date(),
      content: `Hello! I'm your **ForgetLess AI Tutor**.\n\nI have access to your complete memory state. Right now, I can see that **ChromaDB Search** and **FastAPI DI** are at highest forgetting risk — I'll make sure to reinforce these as we talk.\n\nWhat would you like to study today?`,
      boosted: [],
    }
  ]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [concepts, setConcepts]   = useState<ConceptState[]>(MOCK_CONCEPTS);
  const [isMock, setIsMock]       = useState(false);
  const bottomRef                 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    axios.get('/dashboard').then(r => {
      if (r.data?.memory?.length) setConcepts(r.data.memory); setIsMock(false);
    }).catch(() => setIsMock(true));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await axios.post('/chat', {
        message: text,
        history: messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
      });
      const reply: Message = {
        id: (Date.now() + 1).toString(), role: 'assistant',
        content: res.data.reply, timestamp: new Date(),
        boosted: res.data.boosted_concepts ?? [],
      };
      setMessages(prev => [...prev, reply]);
    } catch {
      // Mock response
      const mock = MOCK_RESPONSES[mockIdx % MOCK_RESPONSES.length](text);
      mockIdx++;
      await new Promise(r => setTimeout(r, 1200 + Math.random() * 600));
      const reply: Message = {
        id: (Date.now() + 1).toString(), role: 'assistant',
        content: mock.reply, boosted: mock.boosted, timestamp: new Date(),
      };
      setMessages(prev => [...prev, reply]);
      setIsMock(true);
    } finally {
      setLoading(false);
    }
  };

  const retColor = (r: number) => r >= 0.8 ? 'var(--success)' : r >= 0.55 ? 'var(--warning)' : 'var(--danger)';

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ── Chat area ─────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Header */}
        <div style={{
          padding: 'var(--space-4) var(--space-6)',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-elevated)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 'var(--r-full)',
              background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 16px var(--accent-glow)',
            }}>
              <Brain size={18} color="white" />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>ForgetLess AI Tutor</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                Memory-aware retrieval active
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <span className="badge badge-indigo" style={{ fontSize: '0.68rem' }}>
              <Zap size={9} /> Hybrid Retrieval
            </span>
            <span className="badge badge-warning" style={{ fontSize: '0.68rem' }}>
              <Brain size={9} /> SM-2 Active
            </span>
            {isMock && <span className="badge badge-warning" style={{ fontSize: '0.68rem' }}>Demo Mode</span>}
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <AnimatePresence initial={false}>
            {messages.map(msg => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 12, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                style={{
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  gap: 'var(--space-3)', alignItems: 'flex-start',
                  maxWidth: '85%',
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                {/* Avatar */}
                {msg.role === 'assistant' && (
                  <div style={{
                    width: 32, height: 32, borderRadius: 'var(--r-full)', flexShrink: 0,
                    background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Brain size={14} color="white" />
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {/* Boosted concepts indicator */}
                  {msg.boosted && msg.boosted.length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {msg.boosted.map(b => (
                        <span key={b} style={{
                          fontSize: '0.65rem', padding: '2px 8px', borderRadius: 'var(--r-full)',
                          background: 'var(--danger-bg)', color: 'var(--danger)',
                          border: '1px solid rgba(239,68,68,0.2)',
                          display: 'flex', alignItems: 'center', gap: 3,
                        }}>
                          <AlertTriangle size={9} /> Memory boosted: {b}
                        </span>
                      ))}
                    </div>
                  )}

                  <div style={{
                    padding: 'var(--space-4) var(--space-5)',
                    background: msg.role === 'user' ? 'var(--indigo-900)' : 'var(--bg-elevated)',
                    border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.25)' : 'var(--border)'}`,
                    borderRadius: msg.role === 'user' ? 'var(--r-2xl) var(--r-2xl) var(--r-sm) var(--r-2xl)' : 'var(--r-2xl) var(--r-2xl) var(--r-2xl) var(--r-sm)',
                  }}>
                    {msg.role === 'user' ? (
                      <p style={{ color: 'var(--indigo-300)', fontSize: '0.9rem', lineHeight: 1.6, margin: 0 }}>{msg.content}</p>
                    ) : (
                      <div>{renderMessage(msg.content)}</div>
                    )}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-dimmed)', textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div style={{ width: 32, height: 32, borderRadius: 'var(--r-full)', background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Brain size={14} color="white" />
              </div>
              <div style={{ padding: 'var(--space-4) var(--space-5)', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-2xl) var(--r-2xl) var(--r-2xl) var(--r-sm)', display: 'flex', gap: 4, alignItems: 'center' }}>
                {[0, 1, 2].map(i => (
                  <motion.div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-muted)' }}
                    animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }} />
                ))}
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick prompts */}
        <div style={{ padding: '0 var(--space-6) var(--space-3)', display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {QUICK_PROMPTS.map(p => (
            <button key={p.label} onClick={() => sendMessage(p.text)}
              style={{
                padding: '5px 12px', fontSize: '0.76rem',
                background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                borderRadius: 'var(--r-full)', color: 'var(--text-secondary)',
                cursor: 'pointer', transition: 'all var(--ease-fast)',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.color = 'var(--text-primary)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Input */}
        <form
          onSubmit={e => { e.preventDefault(); sendMessage(input); }}
          style={{ padding: 'var(--space-4) var(--space-6)', borderTop: '1px solid var(--border)', display: 'flex', gap: 'var(--space-3)' }}
        >
          <input
            className="input"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask anything… I'll reinforce what you're forgetting."
            disabled={loading}
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn-primary" disabled={!input.trim() || loading}
            style={{ padding: '12px 20px', opacity: !input.trim() || loading ? 0.5 : 1 }}>
            <Send size={16} />
          </button>
        </form>
      </div>

      {/* ── Memory Sidebar ─────────────────────── */}
      <aside style={{
        width: 264, flexShrink: 0,
        borderLeft: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        overflowY: 'auto',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: 'var(--space-5)', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={14} color="var(--accent)" /> Memory State
          </h3>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
            Live SM-2 retention for each concept
          </p>
        </div>

        <div style={{ padding: 'var(--space-4) var(--space-4)', flex: 1 }}>
          {concepts.map(c => {
            const pct = Math.round(c.retention_prob * 100);
            const col = pct >= 80 ? 'var(--success)' : pct >= 55 ? 'var(--warning)' : 'var(--danger)';
            return (
              <div key={c.concept_id} style={{ marginBottom: 'var(--space-4)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-secondary)' }}>{c.concept_id}</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: col }}>{pct}%</span>
                </div>
                <div style={{ height: 5, background: 'var(--bg-surface)', borderRadius: 3, overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                    style={{ height: '100%', background: col, borderRadius: 3 }}
                  />
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-dimmed)', marginTop: 3 }}>
                  Next review: {c.next_review}
                </div>
              </div>
            );
          })}
        </div>

        {/* Weak concepts section */}
        <div style={{ borderTop: '1px solid var(--border)', padding: 'var(--space-4)' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 'var(--space-3)' }}>
            Critical Weak Spots
          </div>
          {concepts.filter(c => c.retention_prob < 0.65).map(c => (
            <button
              key={c.concept_id}
              onClick={() => sendMessage(`Teach me about ${c.concept_id}. I'm at risk of forgetting it.`)}
              style={{
                width: '100%', textAlign: 'left',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--danger-bg)',
                border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: 'var(--r-md)', marginBottom: 4,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: '0.78rem', color: 'var(--danger)', fontWeight: 500 }}>{c.concept_id}</span>
              <ChevronRight size={12} color="var(--danger)" />
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
};

export default TutorChat;
