import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import gsap from 'gsap';
import { Link } from 'react-router-dom';
import {
  Brain, Sparkles, TrendingUp, Shield, Zap, UploadCloud,
  ArrowRight, ChevronRight, BookOpen, Clock, Star,
} from 'lucide-react';

/* ─── Animated Grid Background ─── */
const GridBackground = () => (
  <div style={{
    position: 'absolute', inset: 0, zIndex: 0, overflow: 'hidden',
    backgroundImage: `
      linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)
    `,
    backgroundSize: '60px 60px',
    maskImage: 'radial-gradient(ellipse 80% 80% at 50% 0%, black 20%, transparent 100%)',
  }} />
);

/* ─── Glow Orb ─── */
const GlowOrb = ({ x, y, color, size }: { x: string; y: string; color: string; size: number }) => (
  <div style={{
    position: 'absolute', left: x, top: y,
    width: size, height: size,
    background: color,
    borderRadius: '50%',
    filter: `blur(${size * 0.6}px)`,
    opacity: 0.35,
    pointerEvents: 'none',
    zIndex: 0,
    transform: 'translate(-50%, -50%)',
  }} />
);

/* ─── Feature Card ─── */
const FeatureCard = ({
  icon, title, desc, gradient, delay,
}: {
  icon: React.ReactNode; title: string; desc: string;
  gradient: string; delay: number;
}) => (
  <motion.div
    className="card"
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ delay, duration: 0.5, ease: 'easeOut' }}
    whileHover={{ y: -4, borderColor: 'var(--border-hover)' }}
    style={{ padding: 'var(--space-8)', cursor: 'default' }}
  >
    <div style={{
      width: 52, height: 52, borderRadius: 'var(--r-xl)',
      background: gradient,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      marginBottom: 'var(--space-5)',
      boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
    }}>
      {icon}
    </div>
    <h3 style={{ fontSize: '1.15rem', marginBottom: 'var(--space-3)', color: 'var(--text-primary)' }}>
      {title}
    </h3>
    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.7 }}>
      {desc}
    </p>
  </motion.div>
);

/* ─── Stat Item ─── */
const StatItem = ({ value, label }: { value: string; label: string }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{
      fontFamily: 'var(--font-display)', fontWeight: 800,
      fontSize: 'clamp(2rem, 4vw, 2.8rem)',
      background: 'linear-gradient(135deg, var(--indigo-300), var(--violet-400))',
      WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
      letterSpacing: '-0.04em',
    }}>{value}</div>
    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 4, fontWeight: 500 }}>
      {label}
    </div>
  </div>
);

/* ─── How It Works Step ─── */
const Step = ({ n, title, desc }: { n: number; title: string; desc: string }) => (
  <motion.div
    initial={{ opacity: 0, x: -20 }}
    whileInView={{ opacity: 1, x: 0 }}
    viewport={{ once: true }}
    transition={{ delay: n * 0.12 }}
    style={{ display: 'flex', gap: 'var(--space-5)', alignItems: 'flex-start' }}
  >
    <div style={{
      flexShrink: 0,
      width: 40, height: 40,
      borderRadius: 'var(--r-full)',
      background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem',
      color: 'white',
      boxShadow: '0 0 20px var(--accent-glow)',
    }}>{n}</div>
    <div>
      <h4 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 'var(--space-2)', color: 'var(--text-primary)' }}>
        {title}
      </h4>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.7 }}>
        {desc}
      </p>
    </div>
  </motion.div>
);

/* ─── Main Landing Page ─── */
const LandingPage = () => {
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!heroRef.current) return;
    const els = heroRef.current.querySelectorAll('[data-hero]');
    gsap.fromTo(
      els,
      { y: 40, opacity: 0, filter: 'blur(4px)' },
      { y: 0, opacity: 1, filter: 'blur(0px)', duration: 0.9, stagger: 0.12, ease: 'power3.out', delay: 0.1 }
    );
  }, []);

  const features = [
    {
      icon: <Brain size={24} color="white" />,
      title: 'Semantic Knowledge Graph',
      desc: 'Your PDFs are parsed, chunked, and embedded into a rich vector space that captures conceptual relationships, not just keywords.',
      gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
      delay: 0,
    },
    {
      icon: <TrendingUp size={24} color="white" />,
      title: 'Ebbinghaus Forgetting Curve',
      desc: 'The SM-2 spaced repetition algorithm tracks memory decay for every concept and surfaces reviews at the exact optimal moment.',
      gradient: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
      delay: 0.1,
    },
    {
      icon: <Sparkles size={24} color="white" />,
      title: 'AI-Generated Answers',
      desc: 'Ask anything in natural language. LangGraph retrieves the most relevant context and a local LLM synthesizes a precise, grounded answer.',
      gradient: 'linear-gradient(135deg, #8b5cf6, #ec4899)',
      delay: 0.2,
    },
    {
      icon: <Shield size={24} color="white" />,
      title: 'Privacy-First Architecture',
      desc: 'Everything runs locally — your documents, embeddings, and memory records never leave your machine.',
      gradient: 'linear-gradient(135deg, #10b981, #059669)',
      delay: 0.3,
    },
    {
      icon: <Clock size={24} color="white" />,
      title: 'Urgency Scoring',
      desc: 'Every concept has a computed urgency score. The system automatically prioritizes what you\'re about to forget.',
      gradient: 'linear-gradient(135deg, #f59e0b, #f97316)',
      delay: 0.4,
    },
    {
      icon: <BookOpen size={24} color="white" />,
      title: 'Persistent Memory',
      desc: 'SQLite-backed memory state persists across sessions. Your learning history grows richer with every review.',
      gradient: 'linear-gradient(135deg, #ec4899, #f43f5e)',
      delay: 0.5,
    },
  ];

  return (
    <div style={{ position: 'relative', overflow: 'hidden' }}>

      {/* ── Hero ───────────────────────────────────── */}
      <section style={{
        position: 'relative', minHeight: '92vh',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: 'var(--space-24) var(--space-6) var(--space-16)',
        textAlign: 'center', overflow: 'hidden',
      }}>
        <GridBackground />
        <GlowOrb x="20%" y="30%" color="radial-gradient(circle, var(--accent-glow), transparent)" size={600} />
        <GlowOrb x="80%" y="60%" color="radial-gradient(circle, var(--violet-glow), transparent)" size={500} />
        <GlowOrb x="50%" y="100%" color="radial-gradient(circle, var(--cyan-glow), transparent)" size={400} />

        <div ref={heroRef} style={{ position: 'relative', zIndex: 1, maxWidth: '900px', width: '100%' }}>

          <div data-hero="" style={{ marginBottom: 'var(--space-6)' }}>
            <span className="badge badge-indigo">
              <Sparkles size={11} /> AI-Powered Spaced Repetition
            </span>
          </div>

          <h1 data-hero="" style={{
            fontSize: 'clamp(3rem, 8vw, 5.5rem)',
            lineHeight: 1.0,
            letterSpacing: '-0.04em',
            marginBottom: 'var(--space-6)',
          }}>
            Remember Everything.
            <br />
            <span className="gradient-text">Forget Nothing.</span>
          </h1>

          <p data-hero="" style={{
            fontSize: 'clamp(1rem, 2vw, 1.2rem)',
            color: 'var(--text-secondary)',
            maxWidth: '600px', margin: '0 auto',
            lineHeight: 1.8, marginBottom: 'var(--space-10)',
          }}>
            Notforgotten ingests your documents into a semantic knowledge graph,
            then uses the Ebbinghaus Forgetting Curve to surface exactly what
            you're about to forget — right before you forget it.
          </p>

          <div data-hero="" style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link to="/session" className="btn-primary" style={{ padding: '14px 28px', fontSize: '1rem' }}>
              <Zap size={16} /> Start Learning
            </Link>
            <Link to="/ingest" className="btn-ghost" style={{ padding: '14px 28px', fontSize: '1rem' }}>
              <UploadCloud size={16} /> Upload PDF <ArrowRight size={14} />
            </Link>
          </div>

          {/* Live preview chip */}
          <motion.div
            data-hero=""
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            style={{
              marginTop: 'var(--space-10)',
              display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)',
              padding: '8px 16px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r-full)',
              color: 'var(--text-muted)', fontSize: '0.8rem',
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', display: 'inline-block', boxShadow: '0 0 8px var(--success)' }} />
            Mock mode active — works offline, real data when backend is running
          </motion.div>
        </div>
      </section>

      {/* ── Stats Bar ─────────────────────────────── */}
      <section style={{ position: 'relative', zIndex: 1 }}>
        <div style={{
          maxWidth: '1280px', margin: '0 auto',
          padding: '0 var(--space-6)',
        }}>
          <motion.div
            className="card"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              padding: 'var(--space-8)',
              gap: 'var(--space-6)',
              background: 'var(--bg-elevated)',
              borderColor: 'var(--border)',
              textAlign: 'center',
            }}
          >
            <StatItem value="SM-2" label="Proven Algorithm" />
            <StatItem value="∞" label="Documents Supported" />
            <StatItem value="100%" label="Local & Private" />
            <StatItem value="AI" label="LangGraph Powered" />
          </motion.div>
        </div>
      </section>

      {/* ── Features ──────────────────────────────── */}
      <section style={{
        maxWidth: '1280px', margin: '0 auto',
        padding: 'var(--space-24) var(--space-6)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-16)' }}>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <span className="badge badge-indigo" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>
              <Star size={11} /> Built Different
            </span>
            <h2 style={{
              fontSize: 'clamp(2rem, 4vw, 2.8rem)',
              letterSpacing: '-0.03em', marginBottom: 'var(--space-4)',
            }}>
              Every layer engineered<br />
              <span className="gradient-text">for deep learning</span>
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '500px', margin: '0 auto' }}>
              A production-grade pipeline from raw PDF to scheduled memory review.
            </p>
          </motion.div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 'var(--space-5)',
        }}>
          {features.map(f => <FeatureCard key={f.title} {...f} />)}
        </div>
      </section>

      {/* ── How It Works ──────────────────────────── */}
      <section style={{
        background: 'var(--bg-elevated)',
        borderTop: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{
          maxWidth: '1280px', margin: '0 auto',
          padding: 'var(--space-24) var(--space-6)',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 'var(--space-16)', alignItems: 'center',
        }}>
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <span className="badge badge-indigo" style={{ marginBottom: 'var(--space-4)', display: 'inline-flex' }}>
              How it Works
            </span>
            <h2 style={{ fontSize: 'clamp(1.8rem, 3vw, 2.4rem)', marginBottom: 'var(--space-8)', letterSpacing: '-0.03em' }}>
              From PDF to<br /><span className="gradient-text">Perfect Recall</span>
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-8)' }}>
              <Step n={1} title="Upload Your Documents" desc="Drag and drop any PDF. The pipeline extracts text using LayoutParser and semantically chunks it via LLM." />
              <Step n={2} title="Build the Knowledge Graph" desc="Chunks are embedded with SentenceTransformers and stored in ChromaDB. Concepts are linked in a Neo4j graph." />
              <Step n={3} title="Query & Learn" desc="Ask questions in natural language. LangGraph retrieves top-k context and an LLM synthesizes a grounded answer." />
              <Step n={4} title="Rate & Schedule" desc="After reviewing, rate how well you remembered. The SM-2 algorithm adjusts your next review date to combat forgetting." />
            </div>
          </motion.div>

          {/* Visual card stack */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            style={{ position: 'relative', height: '420px' }}
          >
            {/* Mock memory card */}
            {[
              { top: '0%', left: '5%', label: 'LangGraph State Machine', urgency: 0.92, rotate: -3 },
              { top: '20%', left: '10%', label: 'Ebbinghaus Forgetting Curve', urgency: 0.76, rotate: 1 },
              { top: '40%', left: '5%', label: 'ChromaDB Vector Search', urgency: 0.61, rotate: -1.5 },
            ].map((card, i) => (
              <motion.div
                key={i}
                className="card"
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 3 + i, repeat: Infinity, delay: i * 0.8 }}
                style={{
                  position: 'absolute', top: card.top, left: card.left,
                  width: '82%', padding: 'var(--space-5)',
                  rotate: `${card.rotate}deg`,
                  background: 'var(--bg-surface)',
                  borderColor: i === 0 ? 'rgba(99,102,241,0.4)' : 'var(--border)',
                  boxShadow: i === 0 ? '0 0 30px rgba(99,102,241,0.15)' : 'none',
                  zIndex: 3 - i,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{card.label}</span>
                  <span className={`badge ${card.urgency > 0.8 ? 'badge-danger' : card.urgency > 0.65 ? 'badge-warning' : 'badge-success'}`}>
                    {Math.round(card.urgency * 100)}% urgency
                  </span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-hover)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${card.urgency * 100}%`, height: '100%', background: card.urgency > 0.8 ? 'var(--danger)' : card.urgency > 0.65 ? 'var(--warning)' : 'var(--success)', borderRadius: 2 }} />
                </div>
                <div style={{ marginTop: 'var(--space-3)', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                  Next review: {i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : 'In 3 days'}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────── */}
      <section style={{
        maxWidth: '1280px', margin: '0 auto',
        padding: 'var(--space-24) var(--space-6)',
        textAlign: 'center',
      }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          style={{
            padding: 'var(--space-16)',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-3xl)',
            position: 'relative', overflow: 'hidden',
          }}
        >
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            width: 600, height: 300,
            background: 'radial-gradient(ellipse, rgba(99,102,241,0.12), transparent 70%)',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
          }} />
          <span className="badge badge-indigo" style={{ marginBottom: 'var(--space-6)', display: 'inline-flex' }}>
            <Zap size={11} /> Ready to Start?
          </span>
          <h2 style={{
            fontSize: 'clamp(2rem, 4vw, 3rem)',
            letterSpacing: '-0.04em', marginBottom: 'var(--space-5)',
          }}>
            Upload a PDF and{' '}
            <span className="gradient-text">start mastering it</span>
            <br />in minutes.
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-10)', fontSize: '1rem' }}>
            No cloud. No accounts. Just AI-powered memory engineering on your machine.
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link to="/ingest" className="btn-primary" style={{ padding: '14px 32px', fontSize: '1rem' }}>
              <UploadCloud size={16} /> Upload Your First PDF
            </Link>
            <Link to="/dashboard" className="btn-ghost" style={{ padding: '14px 32px', fontSize: '1rem' }}>
              View Dashboard <ChevronRight size={14} />
            </Link>
          </div>
        </motion.div>
      </section>

      {/* ── Footer ───────────────────────────────── */}
      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: 'var(--space-8) var(--space-6)',
        textAlign: 'center',
        color: 'var(--text-muted)', fontSize: '0.85rem',
      }}>
        <span>Notforgotten — Built with LangGraph, ChromaDB, FastAPI &amp; React</span>
      </footer>

    </div>
  );
};

export default LandingPage;
