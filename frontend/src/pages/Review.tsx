import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, CircleHelp, Eye, Lightbulb, MessageSquareQuote, PenLine, Repeat2, Sparkles, X, XCircle } from 'lucide-react';
import { api, getCard, type AnswerResult, type Card, type Grade, type SessionSummary } from '../api';
import Md from '../components/Md';
import { Btn, ErrorBox, Flap, Picto, Skeleton, StatusWord, fmtDays, fmtMinutes, pct, useToast } from '../ui';

const KIND: Record<Card['kind'], { label: string; icon: typeof PenLine }> = {
  qa: { label: 'Question', icon: CircleHelp },
  cloze: { label: 'Fill the gap', icon: PenLine },
  explain: { label: 'Explain', icon: Lightbulb },
};

const CONFIDENCE = [
  { v: 0.25, label: 'Guessing' },
  { v: 0.5, label: 'Unsure' },
  { v: 0.75, label: 'Fairly sure' },
  { v: 0.95, label: 'Certain' },
];

const RATINGS = [
  { r: 1, label: 'Again', hint: 'Forgot' },
  { r: 2, label: 'Hard', hint: 'Struggled' },
  { r: 3, label: 'Good', hint: 'Recalled' },
  { r: 4, label: 'Easy', hint: 'Instant' },
];

const MODE_LABEL: Record<string, string> = {
  due: 'Due reviews',
  smart: 'Time-boxed',
  cram: 'Weakest first',
  exam: 'Exam prep',
};

type Phase = 'answer' | 'grading' | 'reveal';

function Prompt({ card }: { card: Card }) {
  if (card.kind === 'cloze') {
    const parts = card.prompt.split('_____');
    return (
      <p className="prompt-text">
        {parts.map((p, i) => (
          <span key={i}>
            {p}
            {i < parts.length - 1 && <span className="blank" aria-label="blank" />}
          </span>
        ))}
      </p>
    );
  }
  return (
    <div className="prompt-text">
      <Md inline>{card.prompt}</Md>
    </div>
  );
}

export default function Review() {
  const [params] = useSearchParams();
  const mode = params.get('mode') ?? 'due';
  const query = useMemo(
    () => ({
      mode,
      minutes: params.get('minutes') ?? undefined,
      concept_id: params.get('concept') ?? undefined,
      document_id: params.get('document') ?? undefined,
      exam_id: params.get('exam') ?? undefined,
    }),
    [params, mode],
  );

  const toast = useToast();
  const [queue, setQueue] = useState<Card[] | null>(null);
  const [sessionId, setSessionId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>('answer');
  const [response, setResponse] = useState('');
  const [confidence, setConfidence] = useState<number | null>(null);
  const [grade, setGrade] = useState<Grade | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<SessionSummary | null>(null);
  const [lastResult, setLastResult] = useState<AnswerResult | null>(null);
  const shownAt = useRef(Date.now());
  const inputRef = useRef<HTMLTextAreaElement & HTMLInputElement>(null);

  useEffect(() => {
    setQueue(null);
    setDone(null);
    setIdx(0);
    api
      .queue(query)
      .then((q) => {
        setQueue(q.cards);
        setSessionId(q.session_id);
      })
      .catch((e) => setError(e.message));
  }, [query]);

  const card = queue?.[idx];

  useEffect(() => {
    shownAt.current = Date.now();
    setPhase('answer');
    setResponse('');
    setConfidence(null);
    setGrade(null);
    window.setTimeout(() => inputRef.current?.focus(), 60);
  }, [card?.id, idx]);

  const check = useCallback(async () => {
    if (!card || phase !== 'answer') return;
    if (!response.trim()) {
      setPhase('reveal');
      return;
    }
    setPhase('grading');
    try {
      setGrade(await api.grade(card.id, response));
    } catch {
      setGrade(null);
    }
    setPhase('reveal');
  }, [card, phase, response]);

  const finish = useCallback(async () => {
    if (!sessionId) return;
    try {
      setDone(await api.session(sessionId));
    } catch {
      setDone({ session_id: sessionId, reviews: 0 });
    }
  }, [sessionId]);

  const rate = useCallback(
    async (rating: number) => {
      if (!card || phase !== 'reveal' || busy) return;
      setBusy(true);
      try {
        const res = await api.answer({
          card_id: card.id,
          rating,
          response: response || undefined,
          score: grade?.score,
          confidence: confidence ?? undefined,
          duration_ms: Date.now() - shownAt.current,
          session_id: sessionId,
        });
        setLastResult(res);
        const before = res.stability_before == null ? 'new' : fmtDays(res.stability_before);
        toast(
          <>
            Memory strength <b>{before}</b> → <b>{fmtDays(res.stability_after)}</b>. Next review in <b>{res.interval}</b>.
          </>,
        );
        let next = queue ?? [];
        if (rating === 1) {
          // Relearn within the session: bring it back a few cards later with fresh intervals.
          const fresh = await getCard(card.id).catch(() => card);
          next = [...next];
          next.splice(Math.min(idx + 4, next.length), 0, { ...fresh, reason: 'again', concept_name: card.concept_name });
          setQueue(next);
        }
        if (idx + 1 >= next.length) await finish();
        else setIdx(idx + 1);
      } catch (e) {
        toast(e instanceof Error ? e.message : 'Could not save that rating.');
      } finally {
        setBusy(false);
      }
    },
    [card, phase, busy, response, grade, confidence, sessionId, queue, idx, toast, finish],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.tagName === 'TEXTAREA' || (e.target as HTMLElement)?.tagName === 'INPUT';
      if (phase === 'answer' && e.key === 'Enter' && (e.metaKey || e.ctrlKey || (e.target as HTMLElement)?.tagName === 'INPUT')) {
        e.preventDefault();
        check();
      } else if (phase === 'reveal' && !typing) {
        if (['1', '2', '3', '4'].includes(e.key)) rate(Number(e.key));
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          rate(grade?.rating ?? 3);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [phase, check, rate, grade]);

  if (error) return <div className="page"><ErrorBox error={error} /></div>;
  if (!queue)
    return (
      <div className="page narrow">
        <Skeleton h={90} />
        <Skeleton h={340} />
      </div>
    );

  if (done) return <Summary summary={done} last={lastResult} />;

  if (queue.length === 0)
    return (
      <>
        <header className="sign on-sign">
          <div className="band">
            <Picto size="lg">
              <CheckCircle2 size={44} />
            </Picto>
            <div style={{ flex: '1 1 320px' }}>
              <h1 className="band-title">Nothing waiting here.</h1>
              <p className="band-sub">Every card in this queue is on schedule. Reviewing early adds little, so spend the time on something new.</p>
            </div>
          </div>
        </header>
        <div className="page narrow" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
          <Btn to="/">Back to Today</Btn>
          <Btn to="/review?mode=cram" variant="secondary" className="on-ground">
            Practise weakest anyway
          </Btn>
          <Btn to="/library" variant="secondary" className="on-ground">
            Add material
          </Btn>
        </div>
      </>
    );

  if (!card) return null;
  const remaining = queue.length - idx;
  const minutesLeft = remaining * 0.4;
  const Kind = KIND[card.kind];
  const suggested = grade?.rating ?? null;

  return (
    <div className="review">
      <header className="sign on-sign review-band">
        <div className="review-band-inner">
          <Picto>
            <Repeat2 size={22} />
          </Picto>
          <div>
            <div style={{ fontWeight: 700 }}>{MODE_LABEL[mode] ?? 'Review'}</div>
            <div className="small">
              Card {Math.min(idx + 1, queue.length)} of {queue.length} · about {fmtMinutes(minutesLeft)} left
            </div>
          </div>
          <div className="ticks" aria-hidden>
            {queue.slice(0, 60).map((c, i) => (
              <i key={`${c.id}-${i}`} className={i < idx ? 'done' : i === idx ? 'now' : ''} />
            ))}
          </div>
          <button className="btn secondary sm plain" onClick={finish} disabled={idx === 0 && phase === 'answer'}>
            <X size={16} /> End session
          </button>
        </div>
      </header>

      <div className="review-stage">
        <AnimatePresence mode="wait">
          <motion.article
            key={`${card.id}-${idx}`}
            className="surface review-card"
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="review-meta">
              <Picto size="sm">
                <Kind.icon size={18} />
              </Picto>
              <span style={{ fontWeight: 700 }}>{Kind.label}</span>
              <span className="muted">·</span>
              <Link to={`/concept/${card.concept_id}`} className="muted" style={{ fontWeight: 500 }}>
                {card.concept_name}
              </Link>
              <span className="spacer" />
              {card.reason === 'again' ? (
                <span className="status rebook chip">RELEARN</span>
              ) : card.is_new ? (
                <span className="status checkin chip">NEW</span>
              ) : (
                <>
                  <span className="mono small muted">recall {pct(card.retrievability)}</span>
                  <StatusWord r={card.retrievability} chip />
                </>
              )}
            </div>

            <Prompt card={card} />

            {phase === 'answer' && (
              <div className="answer-zone">
                <label className="label" htmlFor="answer">
                  {card.kind === 'cloze' ? 'Missing term' : 'Your answer, from memory'}
                </label>
                {card.kind === 'cloze' ? (
                  <input
                    id="answer"
                    ref={inputRef}
                    className="input"
                    value={response}
                    onChange={(e) => setResponse(e.target.value)}
                    placeholder="Type the missing word…"
                    autoComplete="off"
                  />
                ) : (
                  <textarea
                    id="answer"
                    ref={inputRef}
                    className="textarea"
                    value={response}
                    onChange={(e) => setResponse(e.target.value)}
                    placeholder="Write what you remember. Typing it out is what makes it stick."
                  />
                )}
                <div className="confidence">
                  <span className="label">How sure are you?</span>
                  <div className="segmented" role="group" aria-label="Confidence">
                    {CONFIDENCE.map((c) => (
                      <button key={c.v} aria-pressed={confidence === c.v} onClick={() => setConfidence(c.v)}>
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="answer-actions">
                  <Btn onClick={check} icon={<CheckCircle2 size={20} />}>
                    {response.trim() ? 'Check answer' : 'Show answer'}
                  </Btn>
                  <span className="small muted">
                    <span className="kbd">{card.kind === 'cloze' ? 'Enter' : '⌘ Enter'}</span> to check
                  </span>
                </div>
              </div>
            )}

            {phase === 'grading' && (
              <div className="answer-zone">
                <div className="grading mono">
                  <Sparkles size={18} /> <Flap text="GRADING" />
                </div>
              </div>
            )}

            {phase === 'reveal' && (
              <motion.div className="reveal" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                {grade && (
                  <div className={`verdict ${grade.verdict}`}>
                    <div className="verdict-head">
                      {grade.verdict === 'correct' ? <CheckCircle2 size={22} /> : grade.verdict === 'partial' ? <CircleHelp size={22} /> : <XCircle size={22} />}
                      <span className="mono" style={{ fontWeight: 700, letterSpacing: '0.08em' }}>
                        {grade.verdict.toUpperCase()}
                      </span>
                      <span className="score-bar" aria-label={`Score ${Math.round(grade.score * 100)} percent`}>
                        <i style={{ width: `${grade.score * 100}%` }} />
                      </span>
                      <span className="mono small">{Math.round(grade.score * 100)}%</span>
                    </div>
                    {grade.feedback && <p>{grade.feedback}</p>}
                    {grade.missing.length > 0 && (
                      <div className="missing">
                        <span className="label">Missing</span>
                        {grade.missing.map((m) => (
                          <span key={m} className="miss-chip">
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                    {confidence != null && <CalibrationNote confidence={confidence} correct={grade.rating >= 3} />}
                  </div>
                )}
                <div className="answer-box">
                  <span className="label">Answer</span>
                  <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>
                    <Md inline>{card.answer}</Md>
                  </div>
                  {card.explanation && card.explanation !== card.answer && (
                    <div className="muted" style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                      <MessageSquareQuote size={18} style={{ flex: 'none', marginTop: 3 }} />
                      <Md inline>{card.explanation}</Md>
                    </div>
                  )}
                  {response && !grade && (
                    <div className="small muted" style={{ marginTop: 8 }}>
                      You wrote: {response}
                    </div>
                  )}
                </div>

                <div>
                  <div className="label" style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Eye size={16} /> How did it go? {suggested && <span className="muted">Suggested from your answer: {RATINGS[suggested - 1].label}</span>}
                  </div>
                  <div className="ratings">
                    {RATINGS.map((r) => {
                      const p = card.preview?.[String(r.r)];
                      return (
                        <button key={r.r} className={`rating r${r.r}${suggested === r.r ? ' suggested' : ''}`} onClick={() => rate(r.r)} disabled={busy}>
                          <span className="rating-label">{r.label}</span>
                          <span className="rating-when mono">{p ? p.interval : '—'}</span>
                          <span className="rating-hint">
                            {r.hint} <span className="kbd">{r.r}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="small muted" style={{ marginTop: 10 }}>
                    The time under each button is when you'd see this card again. <span className="kbd">Enter</span> takes the suggestion.
                  </p>
                </div>
              </motion.div>
            )}
          </motion.article>
        </AnimatePresence>
      </div>
    </div>
  );
}

function CalibrationNote({ confidence, correct }: { confidence: number; correct: boolean }) {
  const label = CONFIDENCE.find((c) => c.v === confidence)?.label ?? `${Math.round(confidence * 100)}%`;
  let text: string;
  if (correct && confidence >= 0.75) text = `You felt ${label.toLowerCase()} and you were right. Good calibration.`;
  else if (correct) text = `You doubted yourself (“${label}”) but got it. You know this better than you think.`;
  else if (confidence >= 0.75) text = `You felt ${label.toLowerCase()}, but missed it. That gap is the illusion of knowing; this card needs attention.`;
  else text = `You expected to struggle, and did. Honest read.`;
  return <p className="small calib-note">{text}</p>;
}

function Summary({ summary, last }: { summary: SessionSummary; last: AnswerResult | null }) {
  const accuracy = summary.reviews ? (summary.correct ?? 0) / summary.reviews : null;
  return (
    <>
      <header className="sign on-sign">
        <div className="band">
          <Picto size="lg">
            <CheckCircle2 size={44} />
          </Picto>
          <div style={{ flex: '1 1 320px' }}>
            <h1 className="band-title">Session complete.</h1>
            <p className="band-sub">
              {summary.reviews
                ? `You reviewed ${summary.reviews} ${summary.reviews === 1 ? 'card' : 'cards'} across ${summary.concepts} ${summary.concepts === 1 ? 'concept' : 'concepts'}.`
                : 'No cards were rated this time.'}
              {last ? ` The last one comes back in ${last.interval}.` : ''}
            </p>
          </div>
          <div className="band-actions">
            <Btn to="/" size="big">
              Back to Today
            </Btn>
          </div>
        </div>
      </header>
      <div className="page narrow">
        <section className="board">
          <div className="board-head">
            <h2>Session report</h2>
          </div>
          {[
            ['Cards reviewed', String(summary.reviews)],
            ['Recalled', accuracy == null ? '—' : pct(accuracy)],
            ['Time', `${summary.minutes ?? 0} min`],
            ['Memory strength added', `+${Math.max(0, summary.stability_gained_days ?? 0).toFixed(1)} days`],
            ['Average confidence', summary.mean_confidence == null ? '—' : pct(summary.mean_confidence)],
          ].map(([k, v]) => (
            <div className="board-row" key={k} style={{ ['--board-cols' as string]: '1fr auto' }}>
              <span className="name">{k}</span>
              <Flap text={v.toUpperCase()} className="status boarding" />
            </div>
          ))}
        </section>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Btn to="/review?mode=smart&minutes=5" variant="secondary" className="on-ground">
            5 more minutes
          </Btn>
          <Btn to="/insights" variant="secondary" className="on-ground">
            See insights
          </Btn>
        </div>
      </div>
    </>
  );
}
