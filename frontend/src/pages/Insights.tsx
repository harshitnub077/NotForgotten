import { useMemo, useState } from 'react';
import { BarChart3, FlaskConical } from 'lucide-react';
import { api, type FitResult, type Insights as InsightsData } from '../api';
import { Btn, ErrorBox, Flap, SignBand, Skeleton, fmtDays, fmtMinutes, pct, useLoad, useToast } from '../ui';
import { CalibrationPlot, Columns, Heatmap, Legend, LineChart, retrievability } from '../viz';

function ReportBoard({ d }: { d: InsightsData }) {
  const rows: [string, string, string][] = [
    ['Reviews', String(d.reviews_total), `${d.days_studied} days studied`],
    ['Time studied', fmtMinutes(d.minutes_total).toUpperCase(), 'measured per answer'],
    ['Recall rate, last 30 days', pct(d.true_retention.last_30d), `on ${d.true_retention.n} spaced reviews`],
    ['Streak', `${d.streak.current} D`, `longest ${d.streak.longest} days`],
    ['Knowledge banked', `${Math.round(d.knowledge_days)} D`, 'recall-days held over the next year'],
  ];
  return (
    <section className="board">
      <div className="board-head">
        <h2>Memory report</h2>
      </div>
      {rows.map(([k, v, s]) => (
        <div key={k} className="board-row" style={{ ['--board-cols' as string]: '1fr auto' }}>
          <span style={{ minWidth: 0 }}>
            <span className="name" style={{ display: 'block' }}>
              {k}
            </span>
            <span className="sub" style={{ display: 'block' }}>
              {s}
            </span>
          </span>
          <Flap text={v} className="status boarding" />
        </div>
      ))}
    </section>
  );
}

function CalibrationPanel({ d }: { d: InsightsData }) {
  const c = d.calibration;
  let verdict = 'Rate how sure you are before checking answers, and this panel will show whether you can trust that feeling.';
  if (c.n >= 10 && c.overconfidence != null) {
    const over = c.overconfidence;
    if (over > 0.08)
      verdict = `You're overconfident by ${Math.round(over * 100)} points: you feel ${pct(c.mean_confidence)} sure on average but recall ${pct(c.accuracy)}. Familiarity is fooling you; trust the review schedule over the feeling.`;
    else if (over < -0.08)
      verdict = `You're underconfident by ${Math.round(-over * 100)} points: you know more than you think. You can stop re-checking material that's ON TIME.`;
    else verdict = `Well calibrated: your confidence matches your accuracy within ${Math.round(Math.abs(over) * 100)} points. When you feel sure, you usually are.`;
  }
  return (
    <section className="surface">
      <div className="panel-head">
        <h2>Do you know what you know?</h2>
      </div>
      <div className="panel-body calib-grid">
        {c.n > 0 ? <CalibrationPlot bins={c.bins} /> : <div className="muted">No confidence ratings yet.</div>}
        <div className="field-stack">
          <p style={{ fontSize: '1.05rem' }}>{verdict}</p>
          <div className="facts" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <div>
              <span className="label">Answers rated</span>
              <b>{c.n}</b>
            </div>
            <div>
              <span className="label" title="Mean squared gap between confidence and outcome; 0 is perfect">
                Brier score
              </span>
              <b>{c.brier ?? '—'}</b>
            </div>
            <div>
              <span className="label" title="Expected calibration error">
                Calibration error
              </span>
              <b>{c.ece == null ? '—' : pct(c.ece)}</b>
            </div>
          </div>
          <p className="small muted">Dots above the dashed line: you knew more than you felt. Below it: the illusion of knowing.</p>
        </div>
      </div>
    </section>
  );
}

function ModelPanel({ d, onFit }: { d: InsightsData; onFit: () => void }) {
  const [busy, setBusy] = useState(false);
  const [fit, setFit] = useState<FitResult | null>(d.model.last_fit);
  const toast = useToast();
  const run = async () => {
    setBusy(true);
    try {
      const r = await api.optimize();
      setFit(r);
      toast(
        r.improved
          ? `Your personal forgetting curve fits ${Math.round((1 - r.loss_after / r.loss_before) * 100)}% better than the population default.`
          : r.n_predictions < 30
            ? `Needs at least 30 spaced reviews to personalise (you have ${r.n_predictions}).`
            : 'The current model already fits your history best.',
      );
      onFit();
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="surface">
      <div className="panel-head">
        <h2>Your memory model</h2>
        <span className="spacer">
          <span className={`status chip ${d.model.personalized ? 'ontime' : 'checkin'}`}>{d.model.personalized ? 'PERSONALISED' : 'POPULATION DEFAULT'}</span>
        </span>
      </div>
      <div className="panel-body field-stack">
        <p>
          NotForgotten schedules with <b>FSRS-6</b>, a model of each memory's difficulty, stability and recall probability. Fitting it to your own
          history learns how fast <i>you</i> forget.
        </p>
        <div className="facts" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div>
            <span className="label">Predicted recall</span>
            <b>{pct(d.model_fit.predicted)}</b>
          </div>
          <div>
            <span className="label">Actual recall</span>
            <b>{pct(d.model_fit.actual)}</b>
          </div>
          <div>
            <span className="label">Curve decay</span>
            <b>{d.model.decay}</b>
          </div>
        </div>
        {fit && (
          <p className="small">
            Last fit on {fit.n_predictions} reviews: log-loss {fit.loss_before} → {fit.loss_after}, calibration error {pct(fit.rmse_before, 1)} →{' '}
            {pct(fit.rmse_after, 1)}.
          </p>
        )}
        <div>
          <Btn onClick={run} disabled={busy} icon={<FlaskConical size={20} />}>
            {busy ? 'Fitting your curve…' : 'Fit my forgetting curve'}
          </Btn>
        </div>
      </div>
    </section>
  );
}

function CurvePlayground({ decay, desired }: { decay: number; desired: number }) {
  const [s, setS] = useState(7);
  const [target, setTarget] = useState(desired);
  const factor = 0.9 ** (-1 / decay) - 1;
  const interval = (s / factor) * (target ** (-1 / decay) - 1);
  const days = Math.max(30, Math.ceil(interval * 2.2));
  const points = useMemo(() => Array.from({ length: 61 }, (_, i) => (i / 60) * days), [days]);
  return (
    <section className="surface">
      <div className="panel-head">
        <h2>How forgetting works</h2>
      </div>
      <div className="panel-body field-stack">
        <p>
          Recall decays along a power curve: <span className="mono small">R(t) = (1 + F·t/S)^−{decay}</span>. Stability <b>S</b> is the number of days
          until recall drops to 90%. Every successful review at the right moment multiplies it.
        </p>
        <div className="grid cols-2" style={{ gap: 16 }}>
          <label className="field">
            <span className="label">
              Memory strength S: <b>{fmtDays(s)}</b>
            </span>
            <input type="range" min={0.5} max={120} step={0.5} value={s} onChange={(e) => setS(Number(e.target.value))} />
          </label>
          <label className="field">
            <span className="label">
              Review when recall falls to <b>{pct(target)}</b>
            </span>
            <input type="range" min={0.7} max={0.97} step={0.01} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
          </label>
        </div>
        <LineChart
          ariaLabel="Forgetting curve: power law versus exponential"
          series={[
            { name: 'Power law (FSRS)', color: 'var(--c1)', points: points.map((t) => ({ x: t, y: retrievability(t, s, decay) })) },
            { name: 'Exponential (Ebbinghaus)', color: 'var(--c2)', dashed: true, points: points.map((t) => ({ x: t, y: Math.exp((Math.log(0.9) * t) / s) })) },
          ]}
          xFormat={(v) => `${Math.round(v)}d`}
          threshold={{ y: target, label: `review at ${pct(target)} → every ${fmtDays(interval)}` }}
        />
        <Legend
          items={[
            { name: 'Power law (FSRS), fits real reviews', color: 'var(--c1)' },
            { name: 'Exponential (classic Ebbinghaus)', color: 'var(--c2)', dashed: true },
          ]}
        />
      </div>
    </section>
  );
}

export default function Insights() {
  const { data, error, reload } = useLoad(() => api.insights());
  if (error) return <div className="page"><ErrorBox error={error} onRetry={() => reload()} /></div>;
  if (!data)
    return (
      <div className="page">
        <Skeleton h={140} />
        <Skeleton h={300} />
      </div>
    );

  const fc = data.forecast;
  return (
    <>
      <SignBand icon={<BarChart3 size={44} />} title="Insights" sub="Your memory, measured from every answer you've typed. Nothing here is a guess." />
      <div className="page">
        <div className="insights-top">
          <ReportBoard d={data} />
          <section className="surface">
            <div className="panel-head">
              <h2>A year of study</h2>
            </div>
            <div className="panel-body">
              <Heatmap days={data.heatmap} />
            </div>
          </section>
        </div>

        <CalibrationPanel d={data} />

        <div className="grid cols-2">
          <section className="surface">
            <div className="panel-head">
              <h2>Keep up, or stop?</h2>
            </div>
            <div className="panel-body field-stack">
              <LineChart
                ariaLabel="Average recall over the next 30 days with and without reviews"
                series={[
                  { name: 'Keep reviewing', color: 'var(--c1)', points: fc.map((d) => ({ x: d.day, y: d.retention_if_kept })) },
                  { name: 'Stop today', color: 'var(--c2)', dashed: true, points: fc.map((d) => ({ x: d.day, y: d.retention_if_idle })) },
                ]}
                xFormat={(v) => (v === 0 ? 'today' : `+${v}d`)}
              />
              <Legend
                items={[
                  { name: 'Keep reviewing', color: 'var(--c1)' },
                  { name: 'Stop today', color: 'var(--c2)', dashed: true },
                ]}
              />
            </div>
          </section>
          <section className="surface">
            <div className="panel-head">
              <h2>Reviews per day, next 30 days</h2>
            </div>
            <div className="panel-body">
              <Columns
                ariaLabel="Reviews due per day for the next 30 days"
                data={fc.map((d) => ({ label: d.day === 0 ? 'now' : `+${d.day}`, value: d.due }))}
                labelEvery={5}
                tip={(d) => (
                  <>
                    <b>{d.value}</b> reviews · day {d.label}
                  </>
                )}
              />
            </div>
          </section>
        </div>

        <div className="grid cols-2">
          <ModelPanel d={data} onFit={() => reload(true)} />
          <section className="surface">
            <div className="panel-head">
              <h2>How strong your memories are</h2>
            </div>
            <div className="panel-body">
              <Columns
                ariaLabel="Cards by memory strength"
                data={data.stability_histogram.map((b) => ({ label: b.label, value: b.count }))}
                tip={(d) => (
                  <>
                    <b>{d.value}</b> cards hold for {d.label}
                  </>
                )}
              />
              <p className="small muted" style={{ marginTop: 8 }}>
                Memory strength = days until recall falls to 90%. Each well-timed review moves cards to the right.
              </p>
            </div>
          </section>
        </div>

        <CurvePlayground decay={data.model.decay} desired={data.model.desired_retention} />
      </div>
    </>
  );
}
