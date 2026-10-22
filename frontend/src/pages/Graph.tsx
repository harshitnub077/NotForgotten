import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation, type SimulationNodeDatum } from 'd3-force';
import { Clock, Map as MapIcon, Minus, Plus, RotateCcw } from 'lucide-react';
import { api, type GraphData, type GraphNode } from '../api';
import { Btn, ErrorBox, Flap, STATUS, SignBand, StatusWord, pct, statusOf, type StatusKey } from '../ui';

type SimNode = GraphNode & SimulationNodeDatum & { w: number; h: number };
type SimLink = { source: string | SimNode; target: string | SimNode; weight: number; kind: string };

const STOPS = [
  { d: 0, label: 'Today' },
  { d: 7, label: '+1 week' },
  { d: 30, label: '+1 month' },
  { d: 90, label: '+3 months' },
];

const FILL: Record<StatusKey, string> = {
  ontime: 'var(--s-ontime)',
  boarding: 'var(--s-boarding)',
  final: 'var(--s-final)',
  rebook: 'var(--s-rebook)',
  checkin: 'var(--s-checkin)',
};

function nodeWidth(name: string) {
  return Math.min(220, 34 + name.length * 7.4);
}

export default function Graph() {
  const [days, setDays] = useState(0);
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useEffective, setUseEffective] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const nodesRef = useRef<Map<string, SimNode>>(new Map());
  const linksRef = useRef<SimLink[]>([]);
  const simRef = useRef<Simulation<SimNode, SimLink> | null>(null);
  const fitted = useRef(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string | null; startX: number; startY: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [size, setSize] = useState({ w: 900, h: 620 });

  useEffect(() => {
    const t = window.setTimeout(() => {
      api
        .graph(days)
        .then(setData)
        .catch((e) => setError(e.message));
    }, 120);
    return () => window.clearTimeout(t);
  }, [days]);

  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: Math.max(460, Math.min(760, e.contentRect.width * 0.62)) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Update nodes in place so the layout survives time-machine changes.
  useEffect(() => {
    if (!data) return;
    const map = nodesRef.current;
    const docs = Array.from(new Set(data.nodes.map((n) => n.document_id)));
    const anchors = new Map(
      docs.map((d, i) => {
        const a = (i / Math.max(docs.length, 1)) * Math.PI * 2 - Math.PI / 2;
        const r = docs.length > 1 ? Math.min(size.w, size.h) * 0.22 : 0;
        return [d, { x: Math.cos(a) * r, y: Math.sin(a) * r }];
      }),
    );
    const next = new Map<string, SimNode>();
    let structural = !simRef.current || map.size !== data.nodes.length;
    data.nodes.forEach((n) => {
      const prev = map.get(n.id);
      const anchor = anchors.get(n.document_id)!;
      if (prev) {
        // Mutate in place: the simulation holds these objects.
        Object.assign(prev, n);
        next.set(n.id, prev);
      } else {
        structural = true;
        next.set(n.id, {
          ...n,
          x: anchor.x + (Math.random() - 0.5) * 80,
          y: anchor.y + (Math.random() - 0.5) * 80,
          w: nodeWidth(n.name),
          h: 30,
        } as SimNode);
      }
    });
    nodesRef.current = next;
    linksRef.current = data.edges
      .filter((e) => next.has(e.source) && next.has(e.target))
      .map((e) => ({ ...e, source: next.get(e.source)!, target: next.get(e.target)! }));

    if (structural) {
      simRef.current?.stop();
      fitted.current = false;
      const sim = forceSimulation<SimNode, SimLink>(Array.from(next.values()))
        .force('charge', forceManyBody<SimNode>().strength(-240))
        .force(
          'link',
          forceLink<SimNode, SimLink>(linksRef.current)
            .id((d) => d.id)
            .distance((l) => (l.kind === 'related' ? 210 : 120))
            .strength((l) => (l.kind === 'related' ? 0.15 : 0.5)),
        )
        .force('collide', forceCollide<SimNode>().radius((d) => d.w / 2 + 8).iterations(2))
        .force('x', forceX<SimNode>((d) => anchors.get(d.document_id)?.x ?? 0).strength(0.08))
        .force('y', forceY<SimNode>((d) => anchors.get(d.document_id)?.y ?? 0).strength(0.12))
        .alpha(1)
        .on('tick', () => {
          setTick((t) => t + 1);
          if (!fitted.current && sim.alpha() < 0.08) {
            fitted.current = true;
            fitToView();
          }
        });
      simRef.current = sim;
    } else {
      setTick((t) => t + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, size.w, size.h]);

  useEffect(
    () => () => {
      simRef.current?.stop();
      simRef.current = null;
      nodesRef.current = new Map();
    },
    [],
  );

  function fitToView() {
    const all = Array.from(nodesRef.current.values()).filter((n) => n.x != null && n.y != null);
    if (!all.length) return;
    const minX = Math.min(...all.map((n) => n.x! - n.w / 2));
    const maxX = Math.max(...all.map((n) => n.x! + n.w / 2));
    const minY = Math.min(...all.map((n) => n.y! - n.h / 2));
    const maxY = Math.max(...all.map((n) => n.y! + n.h / 2));
    const k = Math.min(1.4, Math.max(0.75, Math.min((size.w - 48) / (maxX - minX || 1), (size.h - 48) / (maxY - minY || 1))));
    setView({ k, x: (-(minX + maxX) / 2) * k, y: (-(minY + maxY) / 2) * k });
  }

  // Wheel zoom needs a non-passive listener so the page doesn't scroll underneath.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setView((v) => ({ ...v, k: Math.min(2.5, Math.max(0.35, v.k * (e.deltaY < 0 ? 1.08 : 1 / 1.08))) }));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const nodes = Array.from(nodesRef.current.values());
  const links = linksRef.current;
  const value = (n: GraphNode) => (useEffective ? n.effective_retention : n.retention);

  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    links.forEach((l) => {
      const s = typeof l.source === 'string' ? l.source : l.source.id;
      const t = typeof l.target === 'string' ? l.target : l.target.id;
      if (!m.has(s)) m.set(s, new Set());
      if (!m.has(t)) m.set(t, new Set());
      m.get(s)!.add(t);
      m.get(t)!.add(s);
    });
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [links.length, data]);

  const learned = nodes.filter((n) => value(n) != null);
  const avg = learned.length ? learned.reduce((s, n) => s + (value(n) ?? 0), 0) / learned.length : null;
  const counts = nodes.reduce(
    (acc, n) => {
      acc[statusOf(value(n))] += 1;
      return acc;
    },
    { ontime: 0, boarding: 0, final: 0, rebook: 0, checkin: 0 } as Record<StatusKey, number>,
  );

  const toLocal = (clientX: number, clientY: number) => {
    const box = svgRef.current!.getBoundingClientRect();
    return { x: (clientX - box.left - size.w / 2 - view.x) / view.k, y: (clientY - box.top - size.h / 2 - view.y) / view.k };
  };

  const onPointerDown = (e: React.PointerEvent, id: string | null) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { id, startX: e.clientX, startY: e.clientY, vx: view.x, vy: view.y, moved: false };
    if (id) {
      const n = nodesRef.current.get(id);
      if (n) {
        n.fx = n.x;
        n.fy = n.y;
        simRef.current?.alphaTarget(0.25).restart();
      }
    }
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    if (Math.abs(e.clientX - d.startX) + Math.abs(e.clientY - d.startY) > 4) d.moved = true;
    if (d.id) {
      const n = nodesRef.current.get(d.id);
      const p = toLocal(e.clientX, e.clientY);
      if (n) {
        n.fx = p.x;
        n.fy = p.y;
      }
    } else {
      setView((v) => ({ ...v, x: d.vx + e.clientX - d.startX, y: d.vy + e.clientY - d.startY }));
    }
  };
  const onPointerUp = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.id) {
      const n = nodesRef.current.get(d.id);
      if (n) {
        n.fx = null;
        n.fy = null;
      }
      simRef.current?.alphaTarget(0);
      if (!d.moved) setSelected(d.id);
    } else if (!d.moved) setSelected(null);
  };
  const zoom = (f: number) => setView((v) => ({ ...v, k: Math.min(2.5, Math.max(0.35, v.k * f)) }));

  const sel = selected ? nodesRef.current.get(selected) : null;
  const focus = hover ?? selected;
  const dayLabel = days === 0 ? 'TODAY' : `+${days} DAYS`;

  return (
    <>
      <SignBand
        icon={<MapIcon size={44} />}
        title="Knowledge map"
        sub="Every concept you're learning, linked by what builds on what. Move the clock forward to see what fades if you stop studying."
      >
        <div className="time-machine">
          <Clock size={22} />
          <div className="tm-readout">
            <Flap text={dayLabel} className="tm-day" />
          </div>
          <input
            type="range"
            min={0}
            max={120}
            step={1}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            aria-label="Days into the future"
            className="tm-range"
          />
          <div className="tm-stops">
            {STOPS.map((s) => (
              <button key={s.d} className={`tm-stop${days === s.d ? ' on' : ''}`} onClick={() => setDays(s.d)}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </SignBand>

      <div className="page">
        {error && <ErrorBox error={error} />}
        <div className="map-layout">
          <section className="map-canvas surface" aria-label="Concept graph">
            <div className="map-toolbar">
              <label className="toggle">
                <input type="checkbox" checked={useEffective} onChange={(e) => setUseEffective(e.target.checked)} />
                Count weak foundations
              </label>
              <span className="spacer" />
              <button className="icon-btn" onClick={() => zoom(1.2)} aria-label="Zoom in">
                <Plus size={16} />
              </button>
              <button className="icon-btn" onClick={() => zoom(1 / 1.2)} aria-label="Zoom out">
                <Minus size={16} />
              </button>
              <button className="icon-btn" onClick={fitToView} aria-label="Fit to view">
                <RotateCcw size={16} />
              </button>
            </div>
            {nodes.length === 0 && data && (
              <div className="map-empty">
                <p>No concepts yet. Add a source in the Library and its concepts will appear here.</p>
                <Btn to="/library">Open Library</Btn>
              </div>
            )}
            <svg
              ref={svgRef}
              width="100%"
              height={size.h}
              viewBox={`${-size.w / 2} ${-size.h / 2} ${size.w} ${size.h}`}
              onPointerDown={(e) => onPointerDown(e, null)}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              style={{ touchAction: 'none', cursor: drag.current ? 'grabbing' : 'grab', display: 'block' }}
            >
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill="var(--ink)" />
                </marker>
              </defs>
              <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
                {links.map((l, i) => {
                  const s = l.source as SimNode;
                  const t = l.target as SimNode;
                  if (s.x == null || t.x == null) return null;
                  const dim = focus && !(s.id === focus || t.id === focus);
                  // stop the arrow at the target's box edge
                  const dx = (t.x ?? 0) - (s.x ?? 0);
                  const dy = (t.y ?? 0) - (s.y ?? 0);
                  const len = Math.hypot(dx, dy) || 1;
                  const sc = Math.min(t.w / 2 / Math.abs(dx || 1e-6), t.h / 2 / Math.abs(dy || 1e-6), 1e6);
                  const pad = Math.min(len - 4, Math.hypot(dx * sc, dy * sc) + 6);
                  return (
                    <line
                      key={i}
                      x1={s.x}
                      y1={s.y}
                      x2={(t.x ?? 0) - (dx / len) * pad}
                      y2={(t.y ?? 0) - (dy / len) * pad}
                      stroke="var(--ink)"
                      strokeOpacity={dim ? 0.12 : l.kind === 'related' ? 0.35 : 0.7}
                      strokeWidth={l.kind === 'related' ? 1 : 1.5}
                      strokeDasharray={l.kind === 'related' ? '4 5' : undefined}
                      markerEnd={l.kind === 'prerequisite' ? 'url(#arrow)' : undefined}
                    />
                  );
                })}
                {nodes.map((n) => {
                  if (n.x == null || n.y == null) return null;
                  const st = statusOf(value(n));
                  const dim = focus && focus !== n.id && !neighbours.get(focus)?.has(n.id);
                  const isSel = selected === n.id;
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x - n.w / 2},${n.y - n.h / 2})`}
                      style={{ cursor: 'pointer', opacity: dim ? 0.25 : 1, transition: 'opacity .2s' }}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        onPointerDown(e, n.id);
                      }}
                      onPointerEnter={() => setHover(n.id)}
                      onPointerLeave={() => setHover(null)}
                      role="button"
                      aria-label={`${n.name}: ${STATUS[st].word}, recall ${pct(value(n))}`}
                    >
                      <rect
                        width={n.w}
                        height={n.h}
                        rx={4}
                        fill={st === 'checkin' ? 'var(--panel)' : 'var(--board)'}
                        stroke={isSel ? 'var(--sign)' : 'var(--ink)'}
                        strokeWidth={isSel ? 3 : 1}
                      />
                      <rect x={6} y={8} width={14} height={14} rx={2} fill={FILL[st]} />
                      <text
                        x={28}
                        y={19.5}
                        fontSize={12.5}
                        fontWeight={700}
                        fill={st === 'checkin' ? 'var(--ink)' : '#f3f3f0'}
                        style={{ fontFamily: 'var(--font)', pointerEvents: 'none' }}
                      >
                        {n.name.length > 26 ? n.name.slice(0, 25) + '…' : n.name}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
            <div className="map-legend">
              {(Object.keys(STATUS) as StatusKey[]).map((k) => (
                <span key={k}>
                  <i style={{ background: FILL[k], outline: k === 'checkin' ? '1px solid var(--ink)' : undefined }} />
                  <b className="mono">{STATUS[k].word}</b> <span className="muted">{STATUS[k].meaning}</span>
                </span>
              ))}
              <span>
                <svg width="34" height="8" aria-hidden>
                  <line x1="0" y1="4" x2="34" y2="4" stroke="var(--ink)" strokeWidth="1.5" />
                </svg>
                builds on
              </span>
              <span>
                <svg width="34" height="8" aria-hidden>
                  <line x1="0" y1="4" x2="34" y2="4" stroke="var(--ink)" strokeDasharray="4 5" />
                </svg>
                related
              </span>
            </div>
          </section>

          <aside className="map-side">
            <section className="board">
              <div className="board-head">
                <h3>
                  <Flap text={dayLabel} />
                </h3>
                <span className="spacer mono small" style={{ color: 'var(--board-dim)' }}>
                  IF YOU STOP NOW
                </span>
              </div>
              <div className="board-row" style={{ ['--board-cols' as string]: '1fr auto' }}>
                <span className="name">Average recall</span>
                <Flap text={pct(avg)} className="status boarding" />
              </div>
              {(['ontime', 'boarding', 'final', 'rebook', 'checkin'] as StatusKey[]).map((k) => (
                <div key={k} className="board-row" style={{ ['--board-cols' as string]: '1fr auto' }}>
                  <span className={`status ${k}`}>{STATUS[k].word}</span>
                  <Flap text={String(counts[k]).padStart(3)} />
                </div>
              ))}
            </section>

            {sel ? (
              <section className="surface">
                <div className="panel-head">
                  <h3>{sel.name}</h3>
                </div>
                <div className="panel-body field-stack">
                  <span className="muted small">{sel.document_title}</span>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <StatusWord r={value(sel)} chip />
                    <span className="mono">{pct(value(sel))}</span>
                  </div>
                  {useEffective && sel.retention != null && sel.effective_retention != null && sel.retention - sel.effective_retention > 0.02 && (
                    <p className="small">
                      Own recall {pct(sel.retention)}, pulled down to {pct(sel.effective_retention)} by fading prerequisites.
                    </p>
                  )}
                  <p className="small muted">
                    {sel.learned}/{sel.cards} cards learned · {sel.due} due now
                  </p>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Btn size="sm" to={`/review?concept=${sel.id}`}>
                      Review
                    </Btn>
                    <Link to={`/concept/${sel.id}`} className="btn secondary sm plain on-ground">
                      Details
                    </Link>
                  </div>
                </div>
              </section>
            ) : (
              <p className="small muted">Select a concept to see its details. Drag to rearrange, scroll to zoom.</p>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
