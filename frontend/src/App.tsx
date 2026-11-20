import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink as RRNavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BrainCircuit, LayoutDashboard, MessageSquare,
  RotateCcw, UploadCloud, Network, Zap,
} from 'lucide-react';

import Dashboard from './components/Dashboard';
import TutorChat from './components/TutorChat';
import ReviewPage from './components/ReviewPage';
import IngestModule from './components/IngestModule';
import KnowledgeGraph from './components/KnowledgeGraph';

/* ── Nav item config ─────────────────────────── */
const NAV = [
  { to: '/', icon: <LayoutDashboard size={17} />, label: 'Dashboard' },
  { to: '/tutor', icon: <MessageSquare size={17} />, label: 'AI Tutor' },
  { to: '/review', icon: <RotateCcw size={17} />, label: 'Review' },
  { to: '/upload', icon: <UploadCloud size={17} />, label: 'Upload' },
  { to: '/graph', icon: <Network size={17} />, label: 'Knowledge Graph' },
];

/* ── Sidebar ─────────────────────────────────── */
const Sidebar = () => {
  const location = useLocation();

  return (
    <aside style={{
      width: 228,
      flexShrink: 0,
      background: 'var(--bg-elevated)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50,
    }}>
      {/* Logo */}
      <div style={{
        padding: 'var(--space-5) var(--space-5)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 'var(--r-lg)',
          background: 'linear-gradient(135deg, var(--indigo-500), var(--violet-500))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 16px var(--accent-glow)',
          flexShrink: 0,
        }}>
          <BrainCircuit size={17} color="white" />
        </div>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', lineHeight: 1.1 }}>
            ForgetLess
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            AI Memory Engine
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav style={{ flex: 1, padding: 'var(--space-4) var(--space-3)', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: '0.67rem', fontWeight: 700, color: 'var(--text-dimmed)', letterSpacing: '0.1em', textTransform: 'uppercase', padding: '8px 10px 6px' }}>
          Navigation
        </div>
        {NAV.map(item => {
          const isActive = location.pathname === item.to;
          return (
            <RRNavLink
              key={item.to}
              to={item.to}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '9px 12px',
                borderRadius: 'var(--r-lg)',
                background: isActive ? 'var(--indigo-900)' : 'transparent',
                color: isActive ? 'var(--indigo-300)' : 'var(--text-secondary)',
                border: isActive ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
                fontWeight: isActive ? 600 : 400,
                fontSize: '0.875rem',
                transition: 'all var(--ease-fast)',
                textDecoration: 'none',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = 'var(--bg-glass)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                  (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
                }
              }}
            >
              <span style={{ opacity: isActive ? 1 : 0.7 }}>{item.icon}</span>
              {item.label}
              {item.to === '/review' && (
                <span style={{
                  marginLeft: 'auto', background: 'var(--danger)', color: 'white',
                  fontSize: '0.65rem', fontWeight: 700,
                  padding: '1px 6px', borderRadius: 'var(--r-full)',
                }}>!</span>
              )}
            </RRNavLink>
          );
        })}
      </nav>

      {/* Bottom status */}
      <div style={{
        padding: 'var(--space-4)',
        borderTop: '1px solid var(--border)',
      }}>
        <div style={{
          padding: 'var(--space-3)',
          background: 'var(--bg-surface)',
          borderRadius: 'var(--r-lg)',
          border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 6px var(--success)' }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Memory Engine
            </span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            SM-2 algorithm active
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Hybrid retrieval enabled
          </div>
        </div>
      </div>
    </aside>
  );
};

/* ── Page Wrapper ────────────────────────────── */
const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.15 } },
};

function AppInner() {
  const location = useLocation();

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{ flex: 1, marginLeft: 228, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            style={{ flex: 1 }}
          >
            <Routes location={location}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tutor" element={<TutorChat />} />
              <Route path="/review" element={<ReviewPage />} />
              <Route path="/upload" element={<IngestModule />} />
              <Route path="/graph" element={<KnowledgeGraph />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppInner />
    </Router>
  );
}
