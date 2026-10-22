import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BookOpen, CalendarClock, Flame, Gauge, Repeat2, Sparkles, Timer, UploadCloud } from 'lucide-react';
import { api, type Job, type Today as TodayData } from '../api';
import { Btn, ErrorBox, Flap, Picto, RecallBar, Skeleton, StatusWord, fmtMinutes, pct, relTime, useLoad } from '../ui';
import { Columns } from '../viz';

export function useDemoLoader(onDone: () => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = async () => {
    setError(null);
    try {
      const { job_id } = await api.loadDemo();
      const poll = async () => {
        const j = await api.job(job_id);
        setJob(j);
        if (j.status === 'running') window.setTimeout(poll, 900);
        else if (j.status === 'done') onDone();
        else setError(j.message);
      };
      poll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return { job, error, start };
}

function FirstRun({ onReady }: { onReady: () => void }) {
  const demo = useDemoLoader(onReady);
  const running = demo.job?.status === 'running';
  return (
    <div className="sign on-sign" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div className="band" style={{ alignItems: 'flex-start', paddingTop: 'clamp(32px, 6vw, 72px)' }}>
        <Picto size="lg">
          <UploadCloud size={44} strokeWidth={2.2} />
        </Picto>
        <div style={{ flex: '1 1 420px' }}>
          <h1 style={{ fontSize: 'clamp(2.6rem, 6vw, 5.4rem)', letterSpacing: '-0.04em' }}>
            Bring what you need to remember.
          </h1>
          <p className="band-sub" style={{ marginTop: 18 }}>
            Add a lecture PDF, your notes or an article. NotForgotten finds the concepts, writes recall questions and schedules
            each one just before you'd forget it.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 28 }}>
            <Btn to="/library" size="big">
              Add study material
            </Btn>
            <Btn variant="secondary" size="big" onClick={demo.start} disabled={running} icon={<Sparkles size={24} />}>
              {running ? 'Preparing demo…' : 'Try the demo library'}
            </Btn>
          </div>
          {demo.job && (
            <div className="board" style={{ marginTop: 24, maxWidth: 640 }}>
              <div className="board-head">
                <h3>
                  <Flap text={demo.job.stage.toUpperCase()} />
                </h3>
                <span className="spacer mono" style={{ color: 'var(--board-dim)' }}>
                  {Math.round(demo.job.progress * 100)}%
                </span>
              </div>
              <div style={{ padding: '0 20px 18px', fontFamily: 'var(--font)' }}>{demo.job.message}</div>
            </div>
          )}
          {demo.error && (
            <div style={{ marginTop: 16 }}>
              <ErrorBox error={demo.error} />
            </div>
          )}
          <p className="small" style={{ marginTop: 22 }}>
            The demo adds three short sample texts and a simulated two-month study history, so every chart has something to show.
            You can remove it in Settings.
          </p>
        </div>
      </div>
    </div>
  );
}

export function ConceptBoard({ rows, title = 'Concept departures', limit = 8 }: { rows: TodayData['at_risk']; title?: string; limit?: number }) {
  return (
    <section className="board" aria-label={title}>
      <div className="board-head">
        <h2>{title}</h2>
        <span className="spacer mono small" style={{ color: 'var(--board-dim)' }}>
          RECALL NOW
        </span>
      </div>
      <div className="board-cols" style={{ ['--board-cols' as string]: '64px 1fr 112px 92px' }}>
        <span>Recall</span>
        <span>Concept</span>
        <span>Status</span>
        <span className="hide-sm">Strength</span>
      </div>
      {rows.length === 0 && <div className="board-empty">NO CONCEPTS STUDIED YET</div>}
      {rows.slice(0, limit).map((c) => (
        <motion.div layout key={c.id} transition={{ type: 'spring', stiffness: 300, damping: 32 }}>
          <Link to={`/concept/${c.id}`} className="board-row" style={{ ['--board-cols' as string]: '64px 1fr 112px 92px' }}>
            <Flap text={pct(c.retention).padStart(4)} />
            <span style={{ minWidth: 0 }}>
              <span className="name" style={{ display: 'block' }}>
                {c.name}
              </span>
              <span className="sub" style={{ display: 'block' }}>
                {c.document_title}
              </span>
            </span>
            <StatusWord r={c.retention} />
            <span className="hide-sm">
              <RecallBar r={c.retention} />
            </span>
          </Link>
        </motion.div>
      ))}
    </section>
  );
}

function useActiveJobs(onFinished: () => void) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const count = useRef(0);
  useEffect(() => {
    let timer = 0;
    const poll = async () => {
      const active = await api.jobs().catch(() => [] as Job[]);
      if (active.length < count.current) onFinished();
      count.current = active.length;
      setJobs(active);
      timer = window.setTimeout(poll, active.length ? 1500 : 15_000);
    };
    poll();
    return () => window.clearTimeout(timer);
  }, [onFinished]);
  return jobs;
}

export default function Today() {
  const { data, error, loading, reload } = useLoad(() => api.today());
  const navigate = useNavigate();
  const quietReload = useCallback(() => reload(true), [reload]);
  const jobs = useActiveJobs(quietReload);

  useEffect(() => {
    const id = window.setInterval(() => reload(true), 60_000);
    return () => window.clearInterval(id);
  }, [reload]);

  if (loading && !data)
    return (
      <div className="page">
        <Skeleton h={260} />
        <Skeleton h={200} />
      </div>
    );
  if (error && !data)
    return (
      <div className="page">
        <ErrorBox error={`Can't reach the NotForgotten server. ${error}`} onRetry={() => reload()} />
      </div>
    );
  if (!data) return null;
  if (data.documents_total === 0 || (data.cards_total === 0 && jobs.length > 0)) return <FirstRun onReady={() => reload()} />;

  const total = data.due + data.new;
  const exam = data.exams[0];
  const week = data.forecast.slice(0, 7);

  return (
    <>
      <section className="sign on-sign" aria-label="Next up">
        <div className="today-grid">
          <div className="next-up">
            <div style={{ display: 'flex', gap: 'clamp(16px, 2vw, 28px)', alignItems: 'flex-start' }}>
              <Picto size="lg">
                <Repeat2 size={46} strokeWidth={2.2} />
              </Picto>
              <div style={{ minWidth: 0 }}>
                {total > 0 ? (
                  <>
                    <h1 className="num" style={{ fontSize: 'clamp(3rem, 7vw, 5.6rem)' }}>
                      Review {total}
                    </h1>
                    <p style={{ fontSize: 'clamp(1.25rem, 2vw, 1.8rem)', fontWeight: 700, marginTop: 10 }}>
                      {data.due} due{data.new ? ` · ${data.new} new` : ''} · about {fmtMinutes(data.estimated_minutes)}
                    </p>
                  </>
                ) : (
                  <>
                    <h1 className="num" style={{ fontSize: 'clamp(3rem, 7vw, 5.6rem)' }}>
                      All clear.
                    </h1>
                    <p style={{ fontSize: 'clamp(1.15rem, 1.8vw, 1.6rem)', fontWeight: 700, marginTop: 10 }}>
                      Next review {relTime(data.next_due)}. Your memory is on schedule.
                    </p>
                  </>
                )}
              </div>
            </div>
            <div className="next-actions">
              {total > 0 ? (
                <Btn to="/review" size="big">
                  Start review
                </Btn>
              ) : (
                <Btn to="/review?mode=cram" size="big">
                  Practise weakest
                </Btn>
              )}
              <div className="short-on-time">
                <span style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Timer size={18} /> Short on time?
                </span>
                <div className="segmented" role="group" aria-label="Time-boxed session">
                  {[5, 10, 20].map((m) => (
                    <button key={m} onClick={() => navigate(`/review?mode=smart&minutes=${m}`)}>
                      {m} min
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <p className="small" style={{ maxWidth: '58ch' }}>
              Time-boxed sessions pick the reviews that protect the most memory per second, not just the oldest due date.
            </p>
          </div>
          <div className="board-slot">
            <ConceptBoard rows={data.at_risk} />
          </div>
        </div>
        <div className="tiles">
          <Link to="/exams" className="tile">
            <Picto>
              <CalendarClock size={22} />
            </Picto>
            <span style={{ minWidth: 0 }}>
              <span className="tile-k" style={{ display: 'block' }}>
                {exam ? exam.name : 'No exam set'}
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                {exam ? `${exam.days_left} days` : 'Plan one'}
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                {exam ? `Target recall ${pct(exam.target)}` : 'Work back from the date'}
              </span>
            </span>
            <span aria-hidden>→</span>
          </Link>
          <Link to="/insights" className="tile">
            <Picto>
              <Flame size={22} />
            </Picto>
            <span>
              <span className="tile-k" style={{ display: 'block' }}>
                Study streak
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                {data.streak.current} {data.streak.current === 1 ? 'day' : 'days'}
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                {data.streak.reviewed_today ? 'Done today' : 'Review today to keep it'} · best {data.streak.longest}
              </span>
            </span>
            <span aria-hidden>→</span>
          </Link>
          <Link to="/map" className="tile">
            <Picto>
              <Gauge size={22} />
            </Picto>
            <span>
              <span className="tile-k" style={{ display: 'block' }}>
                Recall right now
              </span>
              <span className="tile-v" style={{ display: 'block' }}>
                {pct(data.retention_now)}
              </span>
              <span className="tile-s" style={{ display: 'block' }}>
                Across {data.cards_learned} learned cards · aim {pct(data.desired_retention)}
              </span>
            </span>
            <span aria-hidden>→</span>
          </Link>
        </div>
      </section>

      <div className="page">
        {jobs.length > 0 && (
          <section className="board" aria-live="polite">
            {jobs.map((j) => (
              <div key={j.id} className="board-row" style={{ ['--board-cols' as string]: '150px 1fr 60px' }}>
                <Flap text={j.stage.toUpperCase()} className="status boarding" />
                <span className="name" style={{ fontWeight: 500 }}>
                  {j.message}
                </span>
                <span className="mono">{Math.round(j.progress * 100)}%</span>
              </div>
            ))}
          </section>
        )}
        <div className="grid cols-2">
          <section className="surface">
            <div className="panel-head">
              <h2>The week ahead</h2>
              <span className="spacer muted small">reviews due per day if you keep up</span>
            </div>
            <div className="panel-body">
              <Columns
                ariaLabel="Reviews due per day this week"
                data={week.map((d, i) => ({
                  label: i === 0 ? 'Today' : new Date(d.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' }),
                  value: d.due,
                }))}
                tip={(d) => (
                  <>
                    <b>{d.label}</b>: {d.value} reviews
                  </>
                )}
              />
            </div>
          </section>
          <section className="surface">
            <div className="panel-head">
              <h2>Your library</h2>
              <span className="spacer">
                <Btn to="/library" size="sm" variant="secondary">
                  Open
                </Btn>
              </span>
            </div>
            <div className="panel-body stat-list">
              <div>
                <BookOpen size={20} />
                <b>{data.documents_total}</b> sources
              </div>
              <div>
                <Gauge size={20} />
                <b>{data.concepts_total}</b> concepts
              </div>
              <div>
                <Repeat2 size={20} />
                <b>{data.cards_learned}</b> of <b>{data.cards_total}</b> cards learned
              </div>
              <div>
                <Timer size={20} />
                <b>{data.reviewed_today}</b> reviews in the last 24 h
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
