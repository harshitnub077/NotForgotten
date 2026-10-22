import { useEffect, useState } from 'react';
import { Settings as SettingsIcon } from 'lucide-react';
import { api, type Settings as SettingsData } from '../api';
import { Btn, ErrorBox, SignBand, Skeleton, pct, useLoad, useTheme, useToast } from '../ui';

// Relative review load vs. 90% target: interval ∝ (r^(1/−d) − 1), workload ∝ 1/interval.
function relativeLoad(target: number, decay = 0.1542) {
  const iv = (r: number) => r ** (-1 / decay) - 1;
  return iv(0.9) / iv(target);
}

export default function Settings() {
  const { data, error, reload, setData } = useLoad(() => api.settings());
  const [theme, setTheme] = useTheme();
  const toast = useToast();
  const [draft, setDraft] = useState<SettingsData | null>(null);

  useEffect(() => {
    if (data) setDraft(data);
  }, [data]);

  if (error) return <div className="page"><ErrorBox error={error} onRetry={() => reload()} /></div>;
  if (!draft)
    return (
      <div className="page narrow">
        <Skeleton h={300} />
      </div>
    );

  const save = async (patch: Partial<SettingsData>) => {
    try {
      const next = await api.patchSettings(patch);
      setData(next);
      toast('Saved.');
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Could not save.');
    }
  };

  const load = relativeLoad(draft.desired_retention);

  return (
    <>
      <SignBand icon={<SettingsIcon size={44} />} title="Settings" sub="Tune the schedule to your exam pressure and your time." />
      <div className="page narrow">
        <section className="surface">
          <div className="panel-head">
            <h2>Scheduling</h2>
          </div>
          <div className="panel-body field-stack" style={{ gap: 22 }}>
            <label className="field">
              <span className="label">
                Target recall: review a card when its recall falls to <b>{pct(draft.desired_retention)}</b>
              </span>
              <input
                type="range"
                min={0.75}
                max={0.97}
                step={0.01}
                value={draft.desired_retention}
                onChange={(e) => setDraft({ ...draft, desired_retention: Number(e.target.value) })}
                onPointerUp={() => save({ desired_retention: draft.desired_retention })}
                onKeyUp={() => save({ desired_retention: draft.desired_retention })}
              />
              <span className="small">
                About <b>{load.toFixed(1)}×</b> the reviews of a 90% target. Above 93% the cost climbs steeply for little gain; 85–90% suits most
                students.
              </span>
            </label>
            <label className="field">
              <span className="label">New cards per day</span>
              <input
                className="input"
                type="number"
                min={0}
                max={500}
                value={draft.daily_new_limit}
                onChange={(e) => setDraft({ ...draft, daily_new_limit: Number(e.target.value) })}
                onBlur={() => save({ daily_new_limit: draft.daily_new_limit })}
                style={{ maxWidth: 160 }}
              />
              <span className="small muted">Each new card brings roughly 8–10 reviews over the following month.</span>
            </label>
            <label className="field">
              <span className="label">Daily study goal (minutes)</span>
              <input
                className="input"
                type="number"
                min={1}
                max={600}
                value={draft.daily_goal_minutes}
                onChange={(e) => setDraft({ ...draft, daily_goal_minutes: Number(e.target.value) })}
                onBlur={() => save({ daily_goal_minutes: draft.daily_goal_minutes })}
                style={{ maxWidth: 160 }}
              />
            </label>
          </div>
        </section>

        <section className="surface">
          <div className="panel-head">
            <h2>AI</h2>
            <span className="spacer">
              <span className={`status chip ${draft.llm.available ? 'ontime' : 'final'}`}>{draft.llm.available ? 'CONNECTED' : 'OFFLINE'}</span>
            </span>
          </div>
          <div className="panel-body field-stack">
            <p>
              {draft.llm.provider
                ? `Using ${draft.llm.provider} · ${draft.llm.model}.`
                : 'No AI key configured. Add GROQ_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY to the server .env file.'}{' '}
              Without AI, NotForgotten still works: questions come from definitions and key terms, and answers are graded by meaning similarity.
            </p>
            {draft.llm.last_error && <p className="small muted">Last error: {draft.llm.last_error}</p>}
            <label className="toggle">
              <input type="checkbox" checked={draft.use_llm} onChange={(e) => save({ use_llm: e.target.checked })} />
              Use AI for questions, grading and the tutor
            </label>
          </div>
        </section>

        <section className="surface">
          <div className="panel-head">
            <h2>Appearance</h2>
          </div>
          <div className="panel-body">
            <div className="segmented" role="group" aria-label="Theme">
              {(['system', 'light', 'dark'] as const).map((t) => (
                <button key={t} aria-pressed={theme === t} onClick={() => setTheme(t)}>
                  {t === 'system' ? 'Match system' : t === 'light' ? 'Day terminal' : 'Night terminal'}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="surface">
          <div className="panel-head">
            <h2>Data</h2>
          </div>
          <div className="panel-body field-stack">
            <p className="small muted">
              Memory model: {draft.parameters_personalized ? 'personalised to your reviews' : 'population default (FSRS-6)'}. Everything is stored
              locally on this machine.
            </p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Btn
                variant="secondary"
                className="on-ground"
                size="sm"
                onClick={async () => {
                  await api.resetModel();
                  toast('Memory model reset to the population default.');
                  reload(true);
                }}
              >
                Reset memory model
              </Btn>
              <Btn
                variant="danger"
                size="sm"
                onClick={async () => {
                  if (!window.confirm('Remove the demo library and its simulated history?')) return;
                  const r = await api.clearDemo();
                  toast(r.deleted ? `Removed ${r.deleted} demo sources.` : 'No demo sources to remove.');
                }}
              >
                Remove demo library
              </Btn>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
