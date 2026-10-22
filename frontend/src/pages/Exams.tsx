import { useEffect, useState } from 'react';
import { CalendarClock, Trash2 } from 'lucide-react';
import { api, type ExamPlan } from '../api';
import { Btn, ErrorBox, Flap, SignBand, Skeleton, fmtMinutes, pct, useLoad, useToast } from '../ui';
import { Columns } from '../viz';

function BoardingPass({ plan, onDelete }: { plan: ExamPlan; onDelete: () => void }) {
  const onTrack = plan.projected_retention >= plan.target - 0.02;
  return (
    <article className="pass">
      <div className="pass-main">
        <div className="pass-row">
          <div>
            <span className="pass-k">Exam</span>
            <h2 className="pass-name">{plan.name}</h2>
          </div>
          <div className="pass-gate">
            <span className="pass-k">Departs in</span>
            <Flap text={`${plan.days_left}D`} className="pass-big" />
          </div>
        </div>
        <div className="pass-grid">
          <div>
            <span className="pass-k">Date</span>
            <b>{new Date(plan.exam_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</b>
          </div>
          <div>
            <span className="pass-k">Target</span>
            <b>{pct(plan.target)}</b>
          </div>
          <div>
            <span className="pass-k">Cards</span>
            <b>
              {plan.total_cards}
            </b>
          </div>
          <div>
            <span className="pass-k">Still new</span>
            <b>{plan.new_cards}
            </b>
          </div>
          <div>
            <span className="pass-k">Today</span>
            <b>{fmtMinutes(plan.today_minutes)}</b>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
          <Btn to={`/review?mode=exam&exam=${plan.id}`}>Study for this exam</Btn>
          <button className="icon-btn" aria-label={`Delete ${plan.name}`} onClick={onDelete}>
            <Trash2 size={18} />
          </button>
        </div>
      </div>
      <div className="pass-stub">
        <span className="pass-k">On exam day</span>
        <div className="stub-row">
          <span>With this plan</span>
          <Flap text={pct(plan.projected_retention)} className={`status ${onTrack ? 'ontime' : 'final'}`} />
        </div>
        <div className="stub-row">
          <span>If you stop now</span>
          <Flap text={pct(plan.current_retention_at_exam ?? plan.projected_retention_no_plan)} className="status rebook" />
        </div>
        <div className="stub-row">
          <span>Below target</span>
          <Flap text={String(plan.cards_below_target)} />
        </div>
        <span className={`status chip ${onTrack ? 'ontime' : 'final'}`} style={{ alignSelf: 'flex-start', marginTop: 6 }}>
          {onTrack ? 'ON TRACK' : 'ADD STUDY TIME'}
        </span>
      </div>
    </article>
  );
}

function ScheduleBoard({ plan }: { plan: ExamPlan }) {
  const rows = plan.daily.slice(0, 14);
  return (
    <section className="board">
      <div className="board-head">
        <h3>Daily schedule · {plan.name}</h3>
      </div>
      <div className="board-cols" style={{ ['--board-cols' as string]: '1.2fr 1fr 1fr 1fr' }}>
        <span>Day</span>
        <span>Reviews</span>
        <span>New</span>
        <span>Time</span>
      </div>
      {rows.map((d) => (
        <div key={d.day} className="board-row" style={{ ['--board-cols' as string]: '1.2fr 1fr 1fr 1fr' }}>
          <span className="name">{d.day === 0 ? 'Today' : new Date(d.date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</span>
          <span>{d.reviews}</span>
          <span>{d.new}</span>
          <span className="status boarding">{fmtMinutes(d.minutes)}</span>
        </div>
      ))}
      {plan.daily.length > rows.length && <div className="board-empty">+{plan.daily.length - rows.length} MORE DAYS</div>}
    </section>
  );
}

export default function Exams() {
  const exams = useLoad(() => api.exams());
  const docs = useLoad(() => api.documents());
  const [plans, setPlans] = useState<ExamPlan[]>([]);
  const [name, setName] = useState('');
  const [date, setDate] = useState(() => new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10));
  const [target, setTarget] = useState(0.9);
  const [chosen, setChosen] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!exams.data) return;
    Promise.all(exams.data.map((e) => api.exam(e.id))).then(setPlans).catch(() => undefined);
  }, [exams.data]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createExam({ name: name.trim(), exam_date: date, target, document_ids: chosen });
      setName('');
      setChosen([]);
      toast('Exam added. Your daily queue now plans backwards from it.');
      exams.reload(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm('Delete this exam plan?')) return;
    await api.deleteExam(id);
    exams.reload(true);
  };

  const ready = docs.data?.filter((d) => d.status === 'ready') ?? [];

  return (
    <>
      <SignBand
        icon={<CalendarClock size={44} />}
        title="Exams"
        sub="Set the date and the recall you need. NotForgotten simulates every day until then and adds just-in-time final reviews."
      />
      <div className="page">
        <div className="exam-layout">
          <form className="surface" onSubmit={create}>
            <div className="panel-head">
              <h2>New exam</h2>
            </div>
            <div className="panel-body field-stack">
              <label className="field">
                <span className="label">Name</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Biochemistry midterm" required />
              </label>
              <label className="field">
                <span className="label">Date</span>
                <input className="input" type="date" value={date} min={new Date(Date.now() + 86400000).toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} required />
              </label>
              <label className="field">
                <span className="label">
                  Recall you want on the day: <b>{pct(target)}</b>
                </span>
                <input type="range" min={0.7} max={0.97} step={0.01} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
                <span className="small muted">Higher targets cost more daily reviews, sharply above 90%.</span>
              </label>
              <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
                <legend className="label" style={{ marginBottom: 6 }}>
                  Sources on this exam <span className="muted">(none selected = everything)</span>
                </legend>
                {ready.length === 0 && <span className="small muted">Add sources in the Library first.</span>}
                {ready.map((d) => (
                  <label key={d.id} className="toggle" style={{ fontWeight: 500 }}>
                    <input
                      type="checkbox"
                      checked={chosen.includes(d.id)}
                      onChange={(e) => setChosen((c) => (e.target.checked ? [...c, d.id] : c.filter((x) => x !== d.id)))}
                    />
                    {d.title}
                  </label>
                ))}
              </fieldset>
              {error && <ErrorBox error={error} />}
              <div>
                <Btn type="submit" disabled={busy || !name.trim()}>
                  Plan this exam
                </Btn>
              </div>
            </div>
          </form>

          <div className="field-stack" style={{ gap: 20 }}>
            {exams.loading && !exams.data && <Skeleton h={220} />}
            {exams.data && exams.data.length === 0 && (
              <div className="surface panel-body">
                <h3 style={{ marginBottom: 6 }}>No exams yet</h3>
                <p className="muted">Add one and you'll see whether your current pace gets you there, and how many minutes a day it takes.</p>
              </div>
            )}
            {plans.map((p) => (
              <div key={p.id} className="field-stack" style={{ gap: 14 }}>
                <BoardingPass plan={p} onDelete={() => remove(p.id)} />
                <div className="grid cols-2">
                  <ScheduleBoard plan={p} />
                  <section className="surface">
                    <div className="panel-head">
                      <h3>Minutes per day until the exam</h3>
                    </div>
                    <div className="panel-body">
                      <Columns
                        ariaLabel={`Study minutes per day until ${p.name}`}
                        data={p.daily.map((d) => ({ label: d.day === 0 ? 'now' : `+${d.day}`, value: d.minutes }))}
                        labelEvery={Math.max(1, Math.ceil(p.daily.length / 7))}
                        format={(v) => `${Math.round(v)}m`}
                        tip={(d) => (
                          <>
                            <b>{fmtMinutes(d.value)}</b> on day {d.label}
                          </>
                        )}
                      />
                    </div>
                  </section>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
