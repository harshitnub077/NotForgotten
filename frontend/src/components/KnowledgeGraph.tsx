import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Network, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';

/* ── Types ────────────────────────────────────── */
interface GNode {
  id: string;
  retention: number;
  urgency: number;
  file?: string;
  // layout
  x: number; y: number; vx: number; vy: number;
}

interface GEdge { source: string; target: string; }

/* ── Mock data ───────────────────────────────── */
const MOCK_NODES: Omit<GNode, 'x' | 'y' | 'vx' | 'vy'>[] = [
  { id: 'LangGraph', retention: 0.92, urgency: 0.08, file: 'lecture.pdf' },
  { id: 'LangChain', retention: 0.84, urgency: 0.16, file: 'lecture.pdf' },
  { id: 'Ebbinghaus Curve', retention: 0.78, urgency: 0.22, file: 'memory.pdf' },
  { id: 'SM-2 Algorithm', retention: 0.83, urgency: 0.17, file: 'memory.pdf' },
  { id: 'Vector Embeddings', retention: 0.61, urgency: 0.39, file: 'nlp.pdf' },
  { id: 'ChromaDB', retention: 0.47, urgency: 0.53, file: 'nlp.pdf' },
  { id: 'FastAPI', retention: 0.55, urgency: 0.45, file: 'backend.pdf' },
  { id: 'Pydantic', retention: 0.74, urgency: 0.26, file: 'backend.pdf' },
  { id: 'Hybrid Retrieval', retention: 0.68, urgency: 0.32, file: 'retrieval.pdf' },
  { id: 'Forgetting Curve', retention: 0.42, urgency: 0.58, file: 'memory.pdf' },
  { id: 'Spaced Repetition', retention: 0.88, urgency: 0.12, file: 'memory.pdf' },
  { id: 'Knowledge Graph', retention: 0.71, urgency: 0.29, file: 'lecture.pdf' },
];

const MOCK_EDGES: GEdge[] = [
  { source: 'LangChain', target: 'LangGraph' },
  { source: 'LangGraph', target: 'Hybrid Retrieval' },
  { source: 'Hybrid Retrieval', target: 'ChromaDB' },
  { source: 'Hybrid Retrieval', target: 'Vector Embeddings' },
  { source: 'ChromaDB', target: 'Vector Embeddings' },
  { source: 'Ebbinghaus Curve', target: 'Forgetting Curve' },
  { source: 'Forgetting Curve', target: 'SM-2 Algorithm' },
  { source: 'SM-2 Algorithm', target: 'Spaced Repetition' },
  { source: 'FastAPI', target: 'Pydantic' },
  { source: 'FastAPI', target: 'LangGraph' },
  { source: 'Knowledge Graph', target: 'ChromaDB' },
  { source: 'Spaced Repetition', target: 'Ebbinghaus Curve' },
];

/* ── Color by retention ──────────────────────── */
const nodeColor = (r: number) =>
  r >= 0.8 ? '#10b981' : r >= 0.6 ? '#f59e0b' : r >= 0.4 ? '#f97316' : '#ef4444';

/* ── Force simulation (pure JS, no D3) ──────── */
const REPULSION = 4000;
const ATTRACTION = 0.015;
const DAMPING = 0.88;
const CENTER_PULL = 0.005;

function runForceStep(nodes: GNode[], edges: GEdge[], width: number, height: number): GNode[] {
  const next = nodes.map(n => ({ ...n }));
  const cx = width / 2;
  const cy = height / 2;

  // Repulsion between all nodes
  for (let i = 0; i < next.length; i++) {
    for (let j = i + 1; j < next.length; j++) {
      const dx = next[i].x - next[j].x;
      const dy = next[i].y - next[j].y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const force = REPULSION / (dist * dist);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      next[i].vx += fx;
      next[i].vy += fy;
      next[j].vx -= fx;
      next[j].vy -= fy;
    }
  }

  // Attraction along edges
  for (const edge of edges) {
    const ni = next.find(n => n.id === edge.source);
    const nj = next.find(n => n.id === edge.target);
    if (!ni || !nj) continue;
    const dx = nj.x - ni.x;
    const dy = nj.y - ni.y;
    ni.vx += dx * ATTRACTION;
    ni.vy += dy * ATTRACTION;
    nj.vx -= dx * ATTRACTION;
    nj.vy -= dy * ATTRACTION;
  }

  // Center gravity + update positions
  for (const n of next) {
    n.vx += (cx - n.x) * CENTER_PULL;
    n.vy += (cy - n.y) * CENTER_PULL;
    n.vx *= DAMPING;
    n.vy *= DAMPING;
    n.x += n.vx;
    n.y += n.vy;
    const padding = 60;
    n.x = Math.max(padding, Math.min(width - padding, n.x));
    n.y = Math.max(padding, Math.min(height - padding, n.y));
  }
  return next;
}

/* ── Tooltip ─────────────────────────────────── */
const Tooltip = ({ node, offset }: { node: GNode | null; offset: { x: number; y: number } }) => {
  if (!node) return null;
  return (
    <div style={{
      position: 'absolute',
      left: offset.x + 16, top: offset.y - 10,
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--r-lg)', padding: '8px 12px',
      pointerEvents: 'none', zIndex: 10,
      boxShadow: 'var(--shadow-md)',
      minWidth: 180,
    }}>
      <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 6 }}>{node.id}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ fontSize: '0.75rem', color: nodeColor(node.retention) }}>
          Retention: {Math.round(node.retention * 100)}%
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Urgency: {Math.round(node.urgency * 100)}%
        </div>
        {node.file && (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-dimmed)' }}>
            {node.file}
          </div>
        )}
      </div>
      <div style={{ height: 4, background: 'var(--bg-hover)', borderRadius: 2, marginTop: 8, overflow: 'hidden' }}>
        <div style={{ width: `${node.retention * 100}%`, height: '100%', background: nodeColor(node.retention), borderRadius: 2 }} />
      </div>
    </div>
  );
};

/* ── Knowledge Graph ─────────────────────────── */
const KnowledgeGraph = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodes, setNodes] = useState<GNode[]>([]);
  const [edges, setEdges] = useState<GEdge[]>([]);
  const [hovered, setHovered] = useState<GNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [running, setRunning] = useState(true);
  const [isMock, setIsMock] = useState(false);
  const animRef = useRef<number>(0);
  const nodesRef = useRef<GNode[]>([]);

  const W = 900, H = 600;

  /* Initialize nodes scattered around center */
  const initNodes = useCallback((rawNodes: typeof MOCK_NODES, rawEdges: GEdge[]) => {
    const initialized: GNode[] = rawNodes.map((n, i) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 400,
      y: H / 2 + (Math.random() - 0.5) * 300,
      vx: 0, vy: 0,
    }));
    nodesRef.current = initialized;
    setNodes(initialized);
    setEdges(rawEdges);
  }, []);

  /* Load from API or mock */
  useEffect(() => {
    axios.get('/graph').then(r => {
      if (r.data?.nodes?.length) {
        initNodes(r.data.nodes, r.data.edges ?? []);
      } else throw new Error();
    }).catch(() => {
      initNodes(MOCK_NODES, MOCK_EDGES);
      setIsMock(true);
    });
  }, [initNodes]);

  /* Force simulation loop */
  useEffect(() => {
    if (!running) return;
    let step = 0;
    const tick = () => {
      if (step > 300) { setRunning(false); return; } // stabilize after 300 frames
      nodesRef.current = runForceStep(nodesRef.current, edges, W, H);
      setNodes([...nodesRef.current]);
      step++;
      animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [running, edges]);

  const restart = () => {
    initNodes(MOCK_NODES, MOCK_EDGES);
    setRunning(true);
  };

  const nodeRadius = (n: GNode) => 12 + n.urgency * 14;

  return (
    <div style={{ padding: 'var(--space-6)', height: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-5)' }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', marginBottom: 4 }}>Knowledge Graph</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Concepts color-coded by retention strength. Size = urgency. Edges = prerequisites.
          </p>
          {isMock && (
            <span className="badge badge-warning" style={{ marginTop: 6, display: 'inline-flex', fontSize: '0.68rem' }}>
              Demo data — connect backend for real graph
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <button onClick={() => setZoom(z => Math.min(z + 0.15, 2))} className="btn-ghost" style={{ padding: '7px 12px' }}>
            <ZoomIn size={15} />
          </button>
          <button onClick={() => setZoom(z => Math.max(z - 0.15, 0.5))} className="btn-ghost" style={{ padding: '7px 12px' }}>
            <ZoomOut size={15} />
          </button>
          <button onClick={restart} className="btn-ghost" style={{ padding: '7px 12px' }}>
            <RotateCcw size={15} />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 'var(--space-5)', marginBottom: 'var(--space-4)' }}>
        {[
          { color: '#10b981', label: 'Strong (>80%)' },
          { color: '#f59e0b', label: 'Fair (60–80%)' },
          { color: '#f97316', label: 'Weak (40–60%)' },
          { color: '#ef4444', label: 'Critical (<40%)' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: l.color }} />
            {l.label}
          </div>
        ))}
      </div>

      {/* SVG Canvas */}
      <div className="card" style={{
        flex: 1, position: 'relative', overflow: 'hidden',
        background: 'var(--bg-elevated)',
      }}>
        <svg
          ref={svgRef}
          width="100%" height="100%"
          viewBox={`0 0 ${W} ${H}`}
          style={{ display: 'block', transformOrigin: 'center', transform: `scale(${zoom})` }}
        >
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="var(--border-hover)" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map(e => {
            const src = nodes.find(n => n.id === e.source);
            const tgt = nodes.find(n => n.id === e.target);
            if (!src || !tgt) return null;
            return (
              <line
                key={`${e.source}-${e.target}`}
                x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                stroke="var(--border-hover)" strokeWidth={1.5}
                strokeOpacity={0.5}
                markerEnd="url(#arrow)"
              />
            );
          })}

          {/* Nodes */}
          {nodes.map(n => {
            const r = nodeRadius(n);
            const col = nodeColor(n.retention);
            const isHov = hovered?.id === n.id;
            return (
              <g
                key={n.id}
                onMouseEnter={ev => {
                  const rect = svgRef.current?.getBoundingClientRect();
                  if (rect) setTooltipPos({ x: ev.clientX - rect.left, y: ev.clientY - rect.top });
                  setHovered(n);
                }}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Glow ring */}
                {isHov && (
                  <circle cx={n.x} cy={n.y} r={r + 8} fill={col} fillOpacity={0.15} />
                )}
                {/* Urgency pulse for critical */}
                {n.urgency > 0.45 && (
                  <motion.circle
                    cx={n.x} cy={n.y} r={r + 4} fill={col} fillOpacity={0}
                    stroke={col} strokeWidth={1.5}
                    animate={{ r: [r + 4, r + 12], opacity: [0.6, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                )}
                {/* Main node */}
                <circle
                  cx={n.x} cy={n.y} r={r}
                  fill={col}
                  fillOpacity={isHov ? 0.95 : 0.75}
                  stroke={col}
                  strokeWidth={isHov ? 2.5 : 1.5}
                />
                {/* Label */}
                <text
                  x={n.x} y={n.y + r + 14}
                  textAnchor="middle"
                  fill="var(--text-secondary)"
                  fontSize={10}
                  fontFamily="var(--font-sans)"
                  fontWeight={isHov ? 700 : 400}
                >
                  {n.id.length > 14 ? n.id.slice(0, 14) + '…' : n.id}
                </text>
                {/* Retention % inside node */}
                <text
                  x={n.x} y={n.y + 4}
                  textAnchor="middle"
                  fill="white"
                  fontSize={r > 18 ? 10 : 8}
                  fontWeight={700}
                  fontFamily="var(--font-display)"
                >
                  {Math.round(n.retention * 100)}%
                </text>
              </g>
            );
          })}
        </svg>

        {/* Tooltip overlay */}
        <Tooltip node={hovered} offset={tooltipPos} />

        {/* Running indicator */}
        {running && (
          <div style={{
            position: 'absolute', bottom: 12, right: 12,
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: '0.72rem', color: 'var(--text-muted)',
          }}>
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}>
              <Network size={12} />
            </motion.div>
            Simulating forces…
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeGraph;
