import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, Brain, CalendarClock, FileUp, Gauge, Map as MapIcon, PenLine, Repeat2, Sparkles } from 'lucide-react';
import { Btn, Flap, Picto, StatusWord, pct } from '../ui';
import { LineChart, Legend, retrievability } from '../viz';

// Illustrative example only — labelled as such on the page.
const EXAMPLE = [
  { name: 'Krebs cycle', s: 3.2, t: 2.6 },
  { name: 'Backpropagation', s: 9, t: 4 },
  { name: 'Spacing effect', s: 24, t: 6 },
  { name: 'Chemiosmosis', s: 1.6, t: 1.9 },
  { name: 'Glycolysis', s: 14, t: 1 },
  { name: 'Retrieval practice', s: 40, t: 12 },
];

function LiveBoard() {
  const [clock, setClock] = useState(0);
  const [reviewed, setReviewed] = useState<Record<string, number>>({});
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) return;
    const id = window.setInterval(() => setClock((c) => c + 1), 1800);
    return () => window.clearInterval(id);
  }, []);

  // Each tick is half a day; whichever concept falls furthest gets reviewed.
  const rows = useMemo(() => {
    const out = EXAMPLE.map((c) => {
      const since = reviewed[c.name] ?? -c.t;
      const s = reviewed[c.name] != null ? c.s * 2.6 : c.s;
      return { ...c, r: retrievability(clock / 2 - since, s) };
    });
    return out.sort((a, b) => a.r - b.r);
  }, [clock, reviewed]);

  useEffect(() => {
    if (clock > 0 && clock % 3 === 0) {
      const weakest = rows[0];
      setReviewed((r) => ({ ...r, [weakest.name]: clock / 2 }));
    }
    if (clock > 40) {
      setClock(0);
      setReviewed({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock]);

  return (
    <section className="board" aria-label="Example concept board">
      <div className="board-head">
        <h2>Concept departures</h2>
        <span className="spacer mono small" style={{ color: 'var(--board-dim)' }}>
          EXAMPLE · DAY {Math.floor(clock / 2) + 1}
        </span>
      </div>
      {rows.map((c) => (
        <div key={c.name} className="board-row" style={{ ['--board-cols' as string]: '64px 1fr 112px' }}>
          <Flap text={pct(c.r).padStart(4)} />
          <span className="name">{c.name}</span>
          <StatusWord r={c.r} />
        </div>
      ))}
    </section>
  );
}

function Sawtooth() {
  // Recall with reviews at growing intervals vs. cramming once, from the FSRS curve.
  const reviews = [0, 2, 6, 15, 34];
  const stabilities = [2.3, 6.5, 16, 38, 90];
  const points = Array.from({ length: 121 }, (_, i) => i * 0.5);
  const spaced = points.map((t) => {
    let k = 0;
    while (k + 1 < reviews.length && reviews[k + 1] <= t) k++;
    return { x: t, y: retrievability(t - reviews[k], stabilities[k]) };
  });
  const crammed = points.map((t) => ({ x: t, y: retrievability(t, 2.3) }));
  return (
    <div className="field-stack">
      <LineChart
        ariaLabel="Recall over 60 days: spaced reviews versus one cramming session"
        height={240}
        series={[
          { name: 'Spaced reviews', color: 'var(--c1)', points: spaced },
          { name: 'Crammed once', color: 'var(--c2)', points: crammed, dashed: true },
        ]}
        xFormat={(v) => `day ${Math.round(v)}`}
        threshold={{ y: 0.9, label: 'review here' }}
      />
      <Legend
        items={[
          { name: 'Five spaced reviews (about 6 minutes in total)', color: 'var(--c1)' },
          { name: 'One long cramming session', color: 'var(--c2)', dashed: true },
        ]}
      />
    </div>
  );
}

const ROUTE = [
  { icon: FileUp, title: 'Add', text: 'Drop in lecture PDFs, notes or an article.' },
  { icon: BookOpen, title: 'Concepts', text: 'It finds the ideas and links what builds on what.' },
  { icon: PenLine, title: 'Recall', text: 'You type answers from memory; they’re graded on meaning.' },
  { icon: Repeat2, title: 'On schedule', text: 'Each card returns just before you’d forget it.' },
];

const FEATURES = [
  { icon: PenLine, k: 'Typed recall, graded', v: 'No honour-system card flipping. Write what you remember and get marked on meaning, with the points you missed.' },
  { icon: Gauge, k: 'Confidence check', v: 'Say how sure you are first. It measures the gap between feeling ready and being ready.' },
  { icon: MapIcon, k: 'Knowledge map', v: 'Concepts linked by prerequisite. A fading foundation flags everything built on it.' },
  { icon: CalendarClock, k: 'Exam planner', v: 'Pick the date and the recall you need; get minutes per day and a just-in-time final review.' },
  { icon: Brain, k: 'Your own forgetting curve', v: 'FSRS-6 scheduling, fitted to your reviews so intervals match how you forget.' },
  { icon: Sparkles, k: 'Tutor that knows', v: 'Ask anything; answers cite your sources and slip in checks on what is slipping.' },
];

export default function Landing() {
  return (
    <div className="landing">
      <header className="sign on-sign">
        <nav className="land-nav">
          <Link to="/welcome" className="brand" style={{ padding: 0 }}>
            <Picto>
              <svg width="26" height="26" viewBox="0 0 64 64" aria-hidden>
                <path d="M10 32h34M32 18l14 14-14 14" fill="none" stroke="#ffcc00" strokeWidth="8" strokeLinecap="square" />
              </svg>
            </Picto>
            <span className="brand-name">NotForgotten</span>
          </Link>
          <span className="spacer" />
          <Btn to="/" size="sm">
            Open app
          </Btn>
        </nav>
        <div className="land-hero">
          <div className="land-copy">
            <h1 className="land-title">Remember it on exam day.</h1>
            <p className="land-sub">
              NotForgotten turns your PDFs and notes into recall questions, then brings each one back just before you'd forget it, planned backwards
              from your exam.
            </p>
            <div className="land-ctas">
              <Btn to="/" size="big">
                Start studying
              </Btn>
              <Btn to="/library" size="big" variant="secondary" icon={<FileUp size={24} />}>
                Add your first PDF
              </Btn>
            </div>
          </div>
          <div className="land-board">
            <LiveBoard />
            <p className="small" style={{ marginTop: 10 }}>
              Example: recall decays day by day; the weakest concept is reviewed and goes back to ON TIME.
            </p>
          </div>
        </div>
        <div className="tiles">
          <div className="tile">
            <Picto>
              <Repeat2 size={22} />
            </Picto>
            <span>
              <span className="tile-k" style={{ display: 'block' }}>
                Next up
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                Review 14
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                about 9 minutes · example
              </span>
            </span>
            <ArrowRight />
          </div>
          <div className="tile">
            <Picto>
              <CalendarClock size={22} />
            </Picto>
            <span>
              <span className="tile-k" style={{ display: 'block' }}>
                Biochemistry midterm
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                21 days
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                on track for 90% recall · example
              </span>
            </span>
            <ArrowRight />
          </div>
          <div className="tile">
            <Picto>
              <Gauge size={22} />
            </Picto>
            <span>
              <span className="tile-k" style={{ display: 'block' }}>
                Confidence check
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                +12 pts
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                more sure than right · example
              </span>
            </span>
            <ArrowRight />
          </div>
        </div>
      </header>

      <section className="land-section">
        <h2 className="land-h2">From a PDF to memory, in four stops.</h2>
        <ol className="route">
          {ROUTE.map((r, i) => (
            <li key={r.title} className="route-stop">
              <Picto size="lg">
                <r.icon size={36} />
              </Picto>
              <div>
                <h3>{r.title}</h3>
                <p className="muted">{r.text}</p>
              </div>
              {i < ROUTE.length - 1 && <ArrowRight className="route-arrow" size={28} aria-hidden />}
            </li>
          ))}
        </ol>
      </section>

      <section className="land-section land-science">
        <div>
          <h2 className="land-h2">Cramming fades in days. Spacing lasts months.</h2>
          <p className="land-p">
            Each review at the edge of forgetting multiplies how long a memory lasts. The catch is timing it, for hundreds of facts, by hand. That's
            the job NotForgotten does, with the FSRS-6 memory model behind modern spaced repetition.
          </p>
          <p className="small muted" style={{ marginTop: 12 }}>
            Curves computed from the FSRS-6 forgetting model with default parameters; illustrative.
          </p>
        </div>
        <div className="surface panel-body">
          <Sawtooth />
        </div>
      </section>

      <section className="land-section">
        <h2 className="land-h2">What a flashcard app doesn't do.</h2>
        <div className="feature-board">
          {FEATURES.map((f) => (
            <div key={f.k} className="feature">
              <Picto>
                <f.icon size={22} />
              </Picto>
              <div>
                <h3>{f.k}</h3>
                <p className="muted">{f.v}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="sign on-sign land-close">
        <h2 className="land-title" style={{ fontSize: 'clamp(2.4rem, 6vw, 5rem)' }}>
          Your next exam starts today.
        </h2>
        <p className="land-sub">Free and local. Works without an AI key; smarter with one.</p>
        <div className="land-ctas">
          <Btn to="/" size="big">
            Open NotForgotten
          </Btn>
        </div>
      </section>
    </div>
  );
}
