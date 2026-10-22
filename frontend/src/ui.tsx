import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Info, X } from 'lucide-react';

/* ─── Data loading ──────────────────────────────────────── */

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload, setData };
}

/* ─── Memory status vocabulary ──────────────────────────── */

export type StatusKey = 'ontime' | 'boarding' | 'final' | 'rebook' | 'checkin';

export const STATUS: Record<StatusKey, { word: string; meaning: string }> = {
  ontime: { word: 'ON TIME', meaning: 'Recall 90% or higher' },
  boarding: { word: 'BOARDING', meaning: 'Recall 80–90%: review soon' },
  final: { word: 'FINAL CALL', meaning: 'Recall 65–80%: review now' },
  rebook: { word: 'REBOOK', meaning: 'Recall under 65%: relearn it' },
  checkin: { word: 'CHECK IN', meaning: 'Not learned yet' },
};

export function statusOf(r: number | null | undefined): StatusKey {
  if (r === null || r === undefined) return 'checkin';
  r = Math.round(r * 100) / 100; // classify what the board prints
  if (r >= 0.9) return 'ontime';
  if (r >= 0.8) return 'boarding';
  if (r >= 0.65) return 'final';
  return 'rebook';
}

export function StatusWord({ r, chip = false }: { r: number | null | undefined; chip?: boolean }) {
  const key = statusOf(r);
  const word = STATUS[key].word;
  return (
    <span className={`status ${key}${chip ? ' chip' : ''}`} title={STATUS[key].meaning}>
      {key === 'final' ? <span className="blink">{word}</span> : word}
    </span>
  );
}

export function RecallBar({ r }: { r: number | null | undefined }) {
  const on = r == null ? 0 : Math.round(r * 10);
  return (
    <span className={`recall status ${statusOf(r)}`} aria-hidden>
      {Array.from({ length: 10 }, (_, i) => (
        <i key={i} className={i < on ? 'on' : ''} />
      ))}
    </span>
  );
}

export const pct = (r: number | null | undefined, digits = 0) =>
  r == null ? '—' : `${(r * 100).toFixed(digits)}%`;

export function fmtDays(d: number | null | undefined): string {
  if (d == null) return '—';
  if (d < 1 / 24) return `${Math.max(1, Math.round(d * 1440))}m`;
  if (d < 1) return `${Math.round(d * 24)}h`;
  if (d < 30) return `${Math.round(d)}d`;
  if (d < 365) return `${(d / 30.4).toFixed(1)}mo`;
  return `${(d / 365).toFixed(1)}y`;
}

export function fmtMinutes(m: number): string {
  if (m < 1) return m <= 0 ? '0 min' : '<1 min';
  if (m < 60) return `${Math.round(m)} min`;
  const h = Math.floor(m / 60);
  return `${h}h ${Math.round(m - h * 60)}m`;
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(diff);
  const unit =
    abs < 3600 ? `${Math.max(1, Math.round(abs / 60))} min` : abs < 86400 ? `${Math.round(abs / 3600)} h` : `${Math.round(abs / 86400)} d`;
  return diff >= 0 ? `in ${unit}` : `${unit} ago`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
}

/* ─── Split-flap text ───────────────────────────────────── */

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%·';
const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function Flap({ text, className = '' }: { text: string; className?: string }) {
  const [shown, setShown] = useState(text);
  const [turning, setTurning] = useState<boolean[]>([]);
  const prev = useRef(text);

  useEffect(() => {
    if (prev.current === text || reduced()) {
      setShown(text);
      prev.current = text;
      return;
    }
    const from = prev.current.padEnd(text.length);
    prev.current = text;
    const len = text.length;
    let frame = 0;
    const settleAt = Array.from({ length: len }, (_, i) => 3 + i + Math.floor(Math.random() * 3));
    const id = window.setInterval(() => {
      frame += 1;
      const chars: string[] = [];
      const turn: boolean[] = [];
      for (let i = 0; i < len; i++) {
        if (frame >= settleAt[i] || from[i] === text[i] || text[i] === ' ') {
          chars.push(text[i]);
          turn.push(false);
        } else {
          chars.push(GLYPHS[Math.floor(Math.random() * GLYPHS.length)]);
          turn.push(true);
        }
      }
      setShown(chars.join(''));
      setTurning(turn);
      if (frame >= Math.max(...settleAt)) {
        window.clearInterval(id);
        setTurning([]);
      }
    }, 55);
    return () => window.clearInterval(id);
  }, [text]);

  return (
    <span className={`flap ${className}`} aria-label={text}>
      {shown.split('').map((c, i) => (
        <span key={i} aria-hidden className={`flap-ch${turning[i] ? ' turning' : ''}`}>
          {c === ' ' ? ' ' : c}
        </span>
      ))}
    </span>
  );
}

/* ─── Buttons & pictograms ──────────────────────────────── */

type BtnProps = {
  children: ReactNode;
  to?: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'yellow' | 'danger';
  size?: 'sm' | 'md' | 'big';
  icon?: ReactNode;
  disabled?: boolean;
  type?: 'button' | 'submit';
  className?: string;
  title?: string;
};

export function Btn({ children, to, onClick, variant = 'primary', size = 'md', icon, disabled, type = 'button', className = '', title }: BtnProps) {
  const cls = `btn ${variant === 'primary' ? '' : variant} ${size === 'md' ? '' : size} ${className}`.trim();
  const inner = (
    <>
      <span className="arrow" aria-hidden>
        {icon ?? <ArrowRight size={size === 'big' ? 26 : size === 'sm' ? 16 : 20} strokeWidth={2.6} />}
      </span>
      <span>{children}</span>
    </>
  );
  if (to && !disabled)
    return (
      <Link to={to} className={cls} title={title}>
        {inner}
      </Link>
    );
  return (
    <button type={type} className={cls} onClick={onClick} disabled={disabled} title={title}>
      {inner}
    </button>
  );
}

export function Picto({ children, size = 'md', inv = false }: { children: ReactNode; size?: 'sm' | 'md' | 'lg'; inv?: boolean }) {
  return <span className={`picto ${size === 'md' ? '' : size}${inv ? ' inv' : ''}`}>{children}</span>;
}

/* ─── Sign band (page header) ───────────────────────────── */

export function SignBand({
  icon,
  title,
  sub,
  actions,
  children,
}: {
  icon?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="sign on-sign">
      <div className="band">
        {icon && <Picto size="lg">{icon}</Picto>}
        <div style={{ minWidth: 0, flex: '1 1 320px' }}>
          <h1 className="band-title">{title}</h1>
          {sub && <p className="band-sub">{sub}</p>}
        </div>
        {actions && <div className="band-actions">{actions}</div>}
      </div>
      {children}
    </header>
  );
}

/* ─── Toasts ────────────────────────────────────────────── */

type Toast = { id: number; content: ReactNode };
const ToastCtx = createContext<(content: ReactNode) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((content: ReactNode) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, content }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-wrap" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div className="toast" key={t.id}>
            <Info size={18} style={{ flex: 'none', marginTop: 2, color: 'var(--flap)' }} />
            <div style={{ flex: 1 }}>{t.content}</div>
            <button
              className="link-btn"
              aria-label="Dismiss"
              onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}
              style={{ color: 'inherit' }}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/* ─── Theme ─────────────────────────────────────────────── */

export function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>(() => {
    try {
      return (localStorage.getItem('nf-theme') as 'light' | 'dark' | null) ?? 'system';
    } catch {
      return 'system';
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('nf-theme', theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  return [theme, setTheme] as const;
}

/* ─── Small pieces ──────────────────────────────────────── */

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      {error}{' '}
      {onRetry && (
        <button className="link-btn" onClick={onRetry} style={{ color: 'inherit' }}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Skeleton({ h = 120 }: { h?: number }) {
  return <div className="skeleton" style={{ height: h }} />;
}
