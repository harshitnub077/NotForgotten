import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, Brain, Check, Lightbulb, Pause, Pencil, Play, Plus, Trash2, Wand2, X } from 'lucide-react';
import { api, type Card, type ConceptDetail, type Feynman } from '../api';
import Md from '../components/Md';
import { Btn, ErrorBox, Flap, Picto, Skeleton, StatusWord, fmtDays, pct, useLoad, useToast } from '../ui';
import { LineChart } from '../viz';

function LinkList({ title, items, empty }: { title: string; items: ConceptDetail['prerequisites']; empty: string }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>
        {title}
      </div>
      {items.length === 0 && <p className="small muted">{empty}</p>}
      <div className="link-list">
        {items.map((l) => (
          <Link key={l.id} to={`/concept/${l.id}`} className="link-item">
            <span>{l.name}</span>
            <StatusWord r={l.retention} chip />
          </Link>
        ))}
      </div>
    </div>
  );
}

function CardRow({ card, onChange }: { card: Card; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [prompt, setPrompt] = useState(card.prompt);
  const [answer, setAnswer] = useState(card.answer);
  const toast = useToast();

  const save = async () => {
    await api.updateCard(card.id, { prompt, answer });
    setEditing(false);
    toast('Card updated.');
    onChange();
  };

  return (
    <div className={`card-row${card.suspended ? ' suspended' : ''}`}>
      {editing ? (
        <div className="field-stack" style={{ gap: 8, gridColumn: '1 / -1' }}>
          <textarea className="textarea" style={{ minHeight: 70 }} value={prompt} onChange={(e) => setPrompt(e.target.value)} aria-label="Question" />
          <textarea className="textarea" style={{ minHeight: 60 }} value={answer} onChange={(e) => setAnswer(e.target.value)} aria-label="Answer" />
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn size="sm" onClick={save} icon={<Check size={16} />}>
              Save
            </Btn>
            <Btn size="sm" variant="secondary" className="on-ground" onClick={() => setEditing(false)} icon={<X size={16} />}>
              Cancel
            </Btn>
          </div>
        </div>
      ) : (
        <>
          <div style={{ minWidth: 0 }}>
            <div className="card-q">
              <Md inline>{card.prompt}</Md>
            </div>
            <div className="card-a muted">
              <Md inline>{card.answer}</Md>
            </div>
          </div>
          <div className="card-side">
            {card.suspended ? (
              <span className="status chip" style={{ color: 'var(--board-dim)' }}>PAUSED</span>
            ) : card.is_new ? (
              <span className="status checkin chip">NEW</span>
            ) : (
              <StatusWord r={card.retrievability} chip />
            )}
            <span className="mono small muted">{card.is_new ? '—' : `half-life ${fmtDays(card.half_life_days)}`}</span>
            <span className="card-btns">
              <button className="icon-btn" aria-label="Edit card" onClick={() => setEditing(true)}>
                <Pencil size={16} />
              </button>
              <button
                className="icon-btn"
                aria-label={card.suspended ? 'Resume card' : 'Pause card'}
                onClick={async () => {
                  await api.updateCard(card.id, { suspended: !card.suspended });
                  onChange();
                }}
              >
                {card.suspended ? <Play size={16} /> : <Pause size={16} />}
              </button>
              <button
                className="icon-btn"
                aria-label="Delete card"
                onClick={async () => {
                  if (!window.confirm('Delete this card and its review history?')) return;
                  await api.deleteCard(card.id);
                  onChange();
                }}
              >
                <Trash2 size={16} />
              </button>
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function FeynmanPanel({ concept, onDone }: { concept: ConceptDetail; onDone: () => void }) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<Feynman | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.feynman(concept.id, text));
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="surface">
      <div className="panel-head">
        <Picto size="sm">
          <Lightbulb size={18} />
        </Picto>
        <h2>Explain it simply</h2>
      </div>
      <div className="panel-body field-stack">
        <p className="muted">
          The Feynman technique: explain “{concept.name}” to a friend who has never heard of it, without looking at your notes. Gaps in the explanation
          are gaps in your understanding.
        </p>
        <textarea className="textarea" style={{ minHeight: 150 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="In plain words…" />
        <div>
          <Btn onClick={submit} disabled={busy || text.trim().length < 10} icon={<Brain size={20} />}>
            {busy ? 'Reading your explanation…' : 'Check my explanation'}
          </Btn>
        </div>
        {error && <ErrorBox error={error} />}
        {result && (
          <div className="feynman-result">
            <div className="feynman-scores">
              {(
                [
                  ['Overall', result.score],
                  ['Coverage', result.coverage],
                  ['Clarity', result.clarity],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <div className="label">{k}</div>
                  <div className="num" style={{ fontSize: '2.4rem' }}>
                    {pct(v)}
                  </div>
                </div>
              ))}
            </div>
            {result.feedback && <p>{result.feedback}</p>}
            {result.covered.length > 0 && (
              <div className="missing">
                <span className="label">You covered</span>
                {result.covered.map((c) => (
                  <span key={c} className="miss-chip">
                    {c}
                  </span>
                ))}
              </div>
            )}
            {result.missing.length > 0 && (
              <div className="missing">
                <span className="label">Missing</span>
                {result.missing.map((c) => (
                  <span key={c} className="miss-chip" style={{ borderColor: 'var(--bad)' }}>
                    {c}
                  </span>
                ))}
              </div>
            )}
            {result.follow_up && (
              <p className="answer-box" style={{ fontWeight: 700 }}>
                Ask yourself next: {result.follow_up}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function AddCard({ conceptId, onAdded }: { conceptId: string; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState('');
  if (!open)
    return (
      <Btn size="sm" variant="secondary" className="on-ground" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
        Add your own
      </Btn>
    );
  return (
    <form
      className="add-card"
      onSubmit={async (e) => {
        e.preventDefault();
        await api.createCard({ concept_id: conceptId, kind: 'qa', prompt, answer });
        setPrompt('');
        setAnswer('');
        setOpen(false);
        onAdded();
      }}
    >
      <input className="input" placeholder="Question" value={prompt} onChange={(e) => setPrompt(e.target.value)} required minLength={3} />
      <input className="input" placeholder="Answer" value={answer} onChange={(e) => setAnswer(e.target.value)} required />
      <Btn size="sm" type="submit" icon={<Check size={16} />}>
        Add
      </Btn>
      <button type="button" className="icon-btn" aria-label="Cancel" onClick={() => setOpen(false)}>
        <X size={16} />
      </button>
    </form>
  );
}

export default function ConceptPage() {
  const { id = '' } = useParams();
  const { data, error, reload } = useLoad(() => api.concept(id), [id]);
  const toast = useToast();
  const [generating, setGenerating] = useState(false);

  if (error) return <div className="page"><ErrorBox error={error} onRetry={() => reload()} /></div>;
  if (!data)
    return (
      <div className="page">
        <Skeleton h={160} />
        <Skeleton h={300} />
      </div>
    );

  const structural = data.retention != null && data.effective_retention != null && data.retention - data.effective_retention > 0.03;

  return (
    <>
      <header className="sign on-sign">
        <div className="band">
          <div className="concept-gate">
            <Flap text={pct(data.retention)} />
            <span className="small" style={{ fontWeight: 700 }}>
              recall now
            </span>
          </div>
          <div style={{ flex: '1 1 360px', minWidth: 0 }}>
            <p style={{ fontWeight: 700 }}>
              <Link to={`/library/${data.document_id}`}>{data.document_title}</Link>
            </p>
            <h1 className="band-title">{data.name}</h1>
            <p className="band-sub">{data.summary}</p>
          </div>
          <div className="band-actions">
            <Btn to={`/review?concept=${data.id}`} size="big">
              Review this concept
            </Btn>
          </div>
        </div>
      </header>

      <div className="page">
        {structural && (
          <div className="warn-band" role="note">
            <AlertTriangle size={22} style={{ flex: 'none' }} />
            <div>
              <b>Shaky foundations.</b> You recall this at {pct(data.retention)}, but it builds on concepts you're forgetting, so your real grasp is
              closer to {pct(data.effective_retention)}.
              {data.weak_foundations.length > 0 && (
                <>
                  {' '}
                  Revisit{' '}
                  {data.weak_foundations.map((w, i) => (
                    <span key={w.id}>
                      {i ? ', ' : ''}
                      <Link to={`/concept/${w.id}`}>{w.name}</Link>
                    </span>
                  ))}{' '}
                  first.
                </>
              )}
            </div>
          </div>
        )}

        <div className="grid cols-2">
          <section className="surface">
            <div className="panel-head">
              <h2>Forgetting curve</h2>
              <span className="spacer muted small">if you stop reviewing today</span>
            </div>
            <div className="panel-body">
              {data.learned === 0 ? (
                <p className="muted">No curve yet. Review this concept once and NotForgotten starts measuring how fast you forget it.</p>
              ) : (
                <LineChart
                  ariaLabel="Projected recall over the next 90 days"
                  series={[{ name: 'Recall', color: 'var(--c1)', points: data.curve.map((p) => ({ x: p.t, y: p.r })), area: true }]}
                  xFormat={(v) => (v === 0 ? 'today' : `+${v}d`)}
                  threshold={{ y: 0.9, label: 'review line 90%' }}
                />
              )}
              <div className="facts">
                <div>
                  <span className="label">Memory strength</span>
                  <b>{fmtDays(data.stability)}</b>
                </div>
                <div>
                  <span className="label">Difficulty</span>
                  <b>{data.difficulty == null ? '—' : `${data.difficulty.toFixed(1)} / 10`}</b>
                </div>
                <div>
                  <span className="label">Cards learned</span>
                  <b>
                    {data.learned} / {data.cards}
                  </b>
                </div>
                <div>
                  <span className="label">Due now</span>
                  <b>{data.due}</b>
                </div>
              </div>
            </div>
          </section>

          <section className="surface">
            <div className="panel-head">
              <h2>Where it sits</h2>
              <Link to="/map" className="spacer small">
                Open map →
              </Link>
            </div>
            <div className="panel-body field-stack" style={{ gap: 18 }}>
              <LinkList title="Builds on" items={data.prerequisites} empty="Nothing earlier in this source." />
              <LinkList title="Leads to" items={data.dependents} empty="Nothing later depends on it yet." />
              <LinkList title="Related, in other sources" items={data.related} empty="No close matches in other sources." />
              {data.keywords.length > 0 && (
                <div className="missing">
                  <span className="label">Key terms</span>
                  {data.keywords.slice(0, 6).map((k) => (
                    <span key={k} className="miss-chip">
                      {k}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>

        <section className="surface">
          <div className="panel-head" style={{ flexWrap: 'wrap' }}>
            <h2>Recall questions</h2>
            <span className="spacer" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Btn
                size="sm"
                variant="secondary"
                className="on-ground"
                icon={<Wand2 size={16} />}
                disabled={generating}
                onClick={async () => {
                  setGenerating(true);
                  try {
                    const r = await api.generate(data.id, 3);
                    toast(r.created ? `Added ${r.created} new questions.` : 'No new questions found in this material.');
                    reload(true);
                  } finally {
                    setGenerating(false);
                  }
                }}
              >
                {generating ? 'Writing…' : 'Write more'}
              </Btn>
              <AddCard conceptId={data.id} onAdded={() => reload(true)} />
            </span>
          </div>
          <div>
            {data.cards_detail.map((c) => (
              <CardRow key={c.id} card={c} onChange={() => reload(true)} />
            ))}
          </div>
        </section>

        <div className="grid cols-2">
          <FeynmanPanel concept={data} onDone={() => reload(true)} />
          <section className="surface">
            <div className="panel-head">
              <h2>From the source</h2>
            </div>
            <div className="panel-body passages">
              {data.passages.map((p) => (
                <blockquote key={p.id}>
                  <span className="mono small muted">p.{p.page + 1}</span>
                  <p>{p.text}</p>
                </blockquote>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
