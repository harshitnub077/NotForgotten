// Hand-built SVG charts: thin marks, recessive grid, hover tooltips, one y-axis each.
import { useMemo, useRef, useState, type ReactNode } from 'react';

type Pt = { x: number; y: number | null };

export interface Series {
  name: string;
  color: string; // CSS var
  points: Pt[];
  dashed?: boolean;
  area?: boolean;
}

const W = 640;

function ticks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = 0; v <= max + 1e-9; v += step) out.push(+v.toFixed(6));
  if (out[out.length - 1] < max - 1e-9) out.push(+(out[out.length - 1] + step).toFixed(6));
  return out;
}

function useHover() {
  const ref = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ i: number; left: number; top: number } | null>(null);
  return { ref, hover, setHover };
}

/* ─── Line chart (shared y-axis, crosshair tooltip) ───────── */

export function LineChart({
  series,
  height = 220,
  yMax = 1,
  yMin = 0,
  yFormat = (v: number) => `${Math.round(v * 100)}%`,
  xFormat = (v: number) => String(v),
  xLabels,
  threshold,
  ariaLabel,
}: {
  series: Series[];
  height?: number;
  yMax?: number;
  yMin?: number;
  yFormat?: (v: number) => string;
  xFormat?: (v: number) => string;
  xLabels?: number[];
  threshold?: { y: number; label: string };
  ariaLabel: string;
}) {
  const { ref, hover, setHover } = useHover();
  const pad = { l: 44, r: 16, t: 14, b: 26 };
  const xs = series[0]?.points.map((p) => p.x) ?? [];
  const xMin = xs.length ? Math.min(...xs) : 0;
  const xMax = xs.length ? Math.max(...xs) : 1;
  const sx = (x: number) => pad.l + ((x - xMin) / (xMax - xMin || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => pad.t + (1 - (y - yMin) / (yMax - yMin || 1)) * (height - pad.t - pad.b);
  const yt = ticks(yMax - yMin).map((v) => +(v + yMin).toFixed(6)).filter((v) => v <= yMax + 1e-9);

  const paths = series.map((s) => {
    let d = '';
    let started = false;
    s.points.forEach((p) => {
      if (p.y == null) {
        started = false;
        return;
      }
      d += `${started ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`;
      started = true;
    });
    const valid = s.points.filter((p) => p.y != null);
    const area = s.area && valid.length ? `${d}L${sx(valid[valid.length - 1].x)},${sy(yMin)}L${sx(valid[0].x)},${sy(yMin)}Z` : null;
    return { d, area };
  });

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!xs.length) return;
    const box = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - box.left) / box.width) * W;
    let best = 0;
    xs.forEach((v, i) => {
      if (Math.abs(sx(v) - x) < Math.abs(sx(xs[best]) - x)) best = i;
    });
    setHover({ i: best, left: (sx(xs[best]) / W) * box.width, top: 8 });
  };

  const labelsX = xLabels ?? (xs.length ? [xs[0], xs[Math.floor(xs.length / 2)], xs[xs.length - 1]] : []);

  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label={ariaLabel} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {yt.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={W - pad.r} y1={sy(v)} y2={sy(v)} />
            <text className="axis-text" x={pad.l - 8} y={sy(v) + 4} textAnchor="end">
              {yFormat(v)}
            </text>
          </g>
        ))}
        {labelsX.map((v, i) => (
          <text key={`${v}-${i}`} className="axis-text" x={sx(v)} y={height - 6} textAnchor={i === 0 ? 'start' : i === labelsX.length - 1 ? 'end' : 'middle'}>
            {xFormat(v)}
          </text>
        ))}
        {threshold && (
          <g>
            <line x1={pad.l} x2={W - pad.r} y1={sy(threshold.y)} y2={sy(threshold.y)} stroke="var(--ink)" strokeWidth={1} strokeDasharray="2 4" />
            <text className="axis-text" x={W - pad.r} y={sy(threshold.y) - 6} textAnchor="end" style={{ fill: 'var(--ink-2)' }}>
              {threshold.label}
            </text>
          </g>
        )}
        {series.map((s, i) => (
          <g key={s.name}>
            {paths[i].area && <path d={paths[i].area!} fill={s.color} opacity={0.1} />}
            <path d={paths[i].d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={s.dashed ? '5 5' : undefined} />
          </g>
        ))}
        {hover && (
          <g>
            <line x1={sx(xs[hover.i])} x2={sx(xs[hover.i])} y1={pad.t} y2={height - pad.b} stroke="var(--ink-3)" strokeWidth={1} />
            {series.map((s) => {
              const p = s.points[hover.i];
              return p?.y != null ? <circle key={s.name} cx={sx(p.x)} cy={sy(p.y)} r={5} fill={s.color} stroke="var(--panel)" strokeWidth={2} /> : null;
            })}
          </g>
        )}
      </svg>
      {hover && (
        <div className="tip" style={{ left: hover.left, top: hover.top }}>
          <div style={{ fontWeight: 700, marginBottom: 2 }}>{xFormat(xs[hover.i])}</div>
          {series.map((s) => {
            const p = s.points[hover.i];
            return (
              <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 3, background: s.color, display: 'inline-block' }} />
                {s.name}: <b>{p?.y == null ? '—' : yFormat(p.y)}</b>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Legend({ items }: { items: { name: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.name} style={{ color: i.color }}>
          <i className={i.dashed ? 'dash' : ''} style={{ background: i.color }} />
          <span style={{ color: 'var(--ink-2)' }}>{i.name}</span>
        </span>
      ))}
    </div>
  );
}

/* ─── Column chart ──────────────────────────────────────── */

export function Columns({
  data,
  height = 180,
  color = 'var(--c1)',
  format = (v: number) => String(v),
  tip,
  ariaLabel,
  labelEvery = 1,
}: {
  data: { label: string; value: number }[];
  height?: number;
  color?: string;
  format?: (v: number) => string;
  tip?: (d: { label: string; value: number }) => ReactNode;
  ariaLabel: string;
  labelEvery?: number;
}) {
  const { ref, hover, setHover } = useHover();
  const pad = { l: 36, r: 8, t: 18, b: 24 };
  const max = Math.max(1, ...data.map((d) => d.value));
  const yt = ticks(max, 3);
  const top = yt[yt.length - 1] || max;
  const band = (W - pad.l - pad.r) / Math.max(data.length, 1);
  const bw = Math.max(2, Math.min(24, band - 2));
  const sy = (v: number) => pad.t + (1 - v / top) * (height - pad.t - pad.b);

  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label={ariaLabel} onPointerLeave={() => setHover(null)}>
        {yt.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={W - pad.r} y1={sy(v)} y2={sy(v)} />
            <text className="axis-text" x={pad.l - 6} y={sy(v) + 4} textAnchor="end">
              {format(v)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = pad.l + i * band + (band - bw) / 2;
          const y = sy(d.value);
          const h = sy(0) - y;
          const r = Math.min(4, h / 2, bw / 2);
          return (
            <g
              key={i}
              onPointerEnter={(e) => {
                const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setHover({ i, left: ((x + bw / 2) / W) * box.width, top: (y / height) * box.height });
              }}
            >
              <rect x={pad.l + i * band} y={pad.t} width={band} height={height - pad.t - pad.b} fill="transparent" />
              {d.value > 0 && (
                <path
                  d={`M${x},${sy(0)}V${y + r}Q${x},${y} ${x + r},${y}H${x + bw - r}Q${x + bw},${y} ${x + bw},${y + r}V${sy(0)}Z`}
                  fill={color}
                  opacity={hover && hover.i !== i ? 0.55 : 1}
                />
              )}
              {i % labelEvery === 0 && (
                <text className="axis-text" x={x + bw / 2} y={height - 6} textAnchor="middle">
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {hover && data[hover.i] && (
        <div className="tip" style={{ left: hover.left, top: hover.top }}>
          {tip ? tip(data[hover.i]) : `${data[hover.i].label}: ${format(data[hover.i].value)}`}
        </div>
      )}
    </div>
  );
}

/* ─── Year heatmap ──────────────────────────────────────── */

export function Heatmap({ days }: { days: { date: string; count: number; minutes: number }[] }) {
  const { ref, hover, setHover } = useHover();
  const cell = 11;
  const gap = 2;
  const parse = (d: string) => new Date(d + 'T00:00:00');
  const first = days.length ? parse(days[0].date).getDay() : 0;
  const cols = Math.ceil((days.length + first) / 7);
  const max = Math.max(1, ...days.map((d) => d.count));
  const level = (c: number) => (c === 0 ? 0 : Math.min(4, 1 + Math.floor((c / max) * 3.999)));
  const width = cols * (cell + gap) + 28;
  const height = 7 * (cell + gap) + 18;
  const months = useMemo(() => {
    const out: { x: number; label: string }[] = [];
    let last = -1;
    days.forEach((d, i) => {
      const dt = parse(d.date);
      if (dt.getMonth() !== last && dt.getDate() <= 7) {
        out.push({ x: Math.floor((i + first) / 7) * (cell + gap) + 28, label: dt.toLocaleString(undefined, { month: 'short' }) });
        last = dt.getMonth();
      }
    });
    return out;
  }, [days, first]);

  return (
    <div className="chart" ref={ref}>
      <div style={{ overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: 560 }} role="img" aria-label="Reviews per day over the last year" onPointerLeave={() => setHover(null)}>
          {months.map((m) => (
            <text key={m.x} className="axis-text" x={m.x} y={10}>
              {m.label}
            </text>
          ))}
          {['Mon', 'Wed', 'Fri'].map((d, i) => (
            <text key={d} className="axis-text" x={0} y={18 + (1 + i * 2) * (cell + gap) + 9}>
              {d}
            </text>
          ))}
          {days.map((d, i) => {
            const col = Math.floor((i + first) / 7);
            const row = (i + first) % 7;
            const x = 28 + col * (cell + gap);
            const y = 18 + row * (cell + gap);
            return (
              <rect
                key={d.date}
                x={x}
                y={y}
                width={cell}
                height={cell}
                rx={2}
                fill={`var(--heat-${level(d.count)})`}
                onPointerEnter={(e) => {
                  const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                  setHover({ i, left: ((x + cell / 2) / width) * box.width, top: (y / height) * box.height });
                }}
              />
            );
          })}
        </svg>
      </div>
      {hover && days[hover.i] && (
        <div className="tip" style={{ left: hover.left, top: hover.top }}>
          <b>{days[hover.i].count} reviews</b> · {Math.round(days[hover.i].minutes)} min
          <div>{parse(days[hover.i].date).toDateString()}</div>
        </div>
      )}
      <div className="legend" style={{ marginTop: 8, alignItems: 'center' }}>
        <span>Fewer</span>
        {[0, 1, 2, 3, 4].map((l) => (
          <i key={l} style={{ width: 11, height: 11, background: `var(--heat-${l})`, borderRadius: 2 }} />
        ))}
        <span>More reviews</span>
      </div>
    </div>
  );
}

/* ─── Calibration plot ──────────────────────────────────── */

export function CalibrationPlot({ bins }: { bins: { confidence: number; accuracy: number; count: number }[] }) {
  const { ref, hover, setHover } = useHover();
  const S = 280;
  const pad = 38;
  const sx = (v: number) => pad + v * (S - pad - 12);
  const sy = (v: number) => S - pad - v * (S - pad - 12);
  const maxN = Math.max(1, ...bins.map((b) => b.count));
  return (
    <div className="chart" ref={ref} style={{ maxWidth: 320 }}>
      <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label="How sure you felt versus how often you were right" onPointerLeave={() => setHover(null)}>
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line className="grid-line" x1={sx(0)} x2={sx(1)} y1={sy(v)} y2={sy(v)} />
            <line className="grid-line" x1={sx(v)} x2={sx(v)} y1={sy(0)} y2={sy(1)} />
            <text className="axis-text" x={pad - 6} y={sy(v) + 4} textAnchor="end">
              {v * 100}%
            </text>
            <text className="axis-text" x={sx(v)} y={S - 20} textAnchor="middle">
              {v * 100}%
            </text>
          </g>
        ))}
        <text className="axis-text" x={sx(0.5)} y={S - 4} textAnchor="middle">
          how sure you felt →
        </text>
        <text className="axis-text" x={10} y={sy(0.5)} textAnchor="middle" transform={`rotate(-90 10 ${sy(0.5)})`}>
          how often right →
        </text>
        <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="var(--ink)" strokeWidth={1} strokeDasharray="3 4" />
        <path d={bins.map((b, i) => `${i ? 'L' : 'M'}${sx(b.confidence)},${sy(b.accuracy)}`).join('')} fill="none" stroke="var(--c1)" strokeWidth={2} />
        {bins.map((b, i) => (
          <circle
            key={i}
            cx={sx(b.confidence)}
            cy={sy(b.accuracy)}
            r={4 + 6 * Math.sqrt(b.count / maxN)}
            fill="var(--c1)"
            stroke="var(--panel)"
            strokeWidth={2}
            onPointerEnter={(e) => {
              const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
              setHover({ i, left: (sx(b.confidence) / S) * box.width, top: (sy(b.accuracy) / S) * box.height });
            }}
          />
        ))}
      </svg>
      {hover && bins[hover.i] && (
        <div className="tip" style={{ left: hover.left, top: hover.top }}>
          Felt {Math.round(bins[hover.i].confidence * 100)}% sure → right {Math.round(bins[hover.i].accuracy * 100)}%
          <div>{bins[hover.i].count} answers</div>
        </div>
      )}
    </div>
  );
}

/* ─── Forgetting-curve maths (FSRS-6 power law, mirrors the backend) ─── */

export const DECAY_DEFAULT = 0.1542;
export function retrievability(t: number, s: number, decay = DECAY_DEFAULT): number {
  const factor = 0.9 ** (-1 / decay) - 1;
  return s <= 0 ? 0 : (1 + (factor * t) / s) ** -decay;
}
