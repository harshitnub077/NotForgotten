import { useEffect, useState } from 'react';
import { Download, KeyRound, Settings as SettingsIcon, Trash2, UserRound } from 'lucide-react';
import { api, type Settings as SettingsData } from '../api';
import { useAuth } from '../auth';
import { Btn, ErrorBox, SignBand, Skeleton, pct, useLoad, useTheme, useToast } from '../ui';

// Relative review load vs. 90% target: interval ∝ (r^(1/−d) − 1), workload ∝ 1/interval.
function relativeLoad(target: number, decay = 0.1542) {
  const iv = (r: number) => r ** (-1 / decay) - 1;
  return iv(0.9) / iv(target);
}

function AccountPanel() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.name ?? '');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [deletePw, setDeletePw] = useState('');
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const download = () =>
    run(async () => {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `notforgotten-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

  if (!user) return null;
  return (
    <section className="surface">
      <div className="panel-head">
        <h2>Account</h2>
        <span className="spacer muted small">{user.email}</span>
      </div>
      <div className="panel-body field-stack" style={{ gap: 22 }}>
        <form
          className="account-row"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const r = await api.updateProfile(name);
              setUser(r.user);
              toast('Name saved.');
            });
          }}
        >
          <label className="field" style={{ flex: 1 }}>
            <span className="label">Name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </label>
          <Btn type="submit" size="sm" icon={<UserRound size={16} />} disabled={!name.trim() || name === user.name}>
            Save
          </Btn>
        </form>

        <form
          className="account-row"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await api.changePassword(current, next);
              setCurrent('');
              setNext('');
              toast('Password changed. Other devices were signed out.');
            });
          }}
        >
          <label className="field" style={{ flex: 1 }}>
            <span className="label">Current password</span>
            <input className="input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
          </label>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">New password</span>
            <input className="input" type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={8} />
          </label>
          <Btn type="submit" size="sm" icon={<KeyRound size={16} />} disabled={!current || next.length < 8}>
            Change
          </Btn>
        </form>

        <div className="account-row" style={{ alignItems: 'center' }}>
          <p className="small" style={{ flex: 1 }}>
            Download everything NotForgotten stores about you: sources, cards, reviews, exams and settings, as JSON.
          </p>
          <Btn size="sm" variant="secondary" className="on-ground" icon={<Download size={16} />} onClick={download}>
            Export my data
          </Btn>
        </div>

        <form
          className="account-row danger-zone"
          onSubmit={(e) => {
            e.preventDefault();
            if (!window.confirm('Delete your account and everything in it? This cannot be undone.')) return;
            run(async () => {
              await api.deleteAccount(deletePw);
              setUser(null);
            });
          }}
        >
          <label className="field" style={{ flex: 1 }}>
            <span className="label">Delete account: confirm with your password</span>
            <input className="input" type="password" value={deletePw} onChange={(e) => setDeletePw(e.target.value)} autoComplete="current-password" />
          </label>
          <Btn type="submit" size="sm" variant="danger" icon={<Trash2 size={16} />} disabled={!deletePw}>
            Delete account
          </Btn>
        </form>
        {error && <ErrorBox error={error} />}
      </div>
    </section>
  );
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
        <AccountPanel />
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
              Memory model: {draft.parameters_personalized ? 'personalised to your reviews' : 'population default (FSRS-6)'}. Your library is private to your account.
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
