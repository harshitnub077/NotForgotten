import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookmarkPlus, MessageSquareText, Send, Square } from 'lucide-react';
import { api, streamTutor, type SearchHit } from '../api';
import Md from '../components/Md';
import { Btn, SignBand, StatusWord, pct, useLoad, useToast } from '../ui';

type Msg = {
  role: 'user' | 'assistant';
  content: string;
  sources?: SearchHit[];
  fading?: { id: string; name: string; retention: number }[];
  streaming?: boolean;
  saved?: boolean;
};

const MODES = [
  { id: 'explain', label: 'Explain', hint: 'Clear answers, then one recall check' },
  { id: 'socratic', label: 'Socratic', hint: 'Guides you with questions' },
  { id: 'quiz', label: 'Quiz me', hint: 'Tests what is fading' },
];

export default function Tutor() {
  const [mode, setMode] = useState('explain');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const toast = useToast();
  const today = useLoad(() => api.today());

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setInput('');
    setBusy(true);
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: 'user', content: message }, { role: 'assistant', content: '', streaming: true }]);
    const controller = new AbortController();
    abortRef.current = controller;
    const patchLast = (fn: (m: Msg) => Msg) => setMessages((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    try {
      await streamTutor(
        { message, history, mode },
        (e) => {
          if (e.type === 'meta') patchLast((m) => ({ ...m, sources: e.sources, fading: e.fading }));
          else if (e.type === 'token') patchLast((m) => ({ ...m, content: m.content + e.text }));
          else if (e.type === 'error') patchLast((m) => ({ ...m, content: m.content + `\n\n_${e.message}_` }));
        },
        controller.signal,
      );
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError'))
        patchLast((m) => ({ ...m, content: m.content || (e instanceof Error ? e.message : 'Something went wrong.') }));
    } finally {
      patchLast((m) => ({ ...m, streaming: false }));
      setBusy(false);
      abortRef.current = null;
      taRef.current?.focus();
    }
  };

  const saveCards = async (i: number) => {
    const m = messages[i];
    const concept = m.sources?.[0]?.concept_id;
    if (!concept) {
      toast('This answer has no source concept to attach cards to.');
      return;
    }
    try {
      const r = await api.cardsFromChat(m.content, concept);
      setMessages((all) => all.map((x, j) => (j === i ? { ...x, saved: true } : x)));
      toast(`Added ${r.created} recall questions to “${m.sources?.[0]?.concept_name}”.`);
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Could not create cards.');
    }
  };

  const fading = today.data?.at_risk.filter((c) => c.retention < 0.85).slice(0, 3) ?? [];
  const suggestions = fading.length
    ? [`Quiz me on ${fading[0].name}`, ...fading.slice(1).map((c) => `Explain ${c.name} simply`), 'What am I most likely to forget this week?']
    : ['Summarise the key ideas in my library', 'Quiz me on anything', 'What should I study first?'];

  return (
    <div className="tutor">
      <SignBand
        icon={<MessageSquareText size={44} />}
        title="Tutor"
        sub="Ask anything about your material. Answers cite your sources and slip in quick checks on what you're forgetting."
        actions={
          <div className="segmented mode-switch" role="group" aria-label="Teaching mode">
            {MODES.map((m) => (
              <button key={m.id} aria-pressed={mode === m.id} onClick={() => setMode(m.id)} title={m.hint}>
                {m.label}
              </button>
            ))}
          </div>
        }
      />
      <div className="chat">
        <div className="chat-scroll">
          {messages.length === 0 && (
            <div className="chat-empty">
              <h2>What do you want to understand?</h2>
              <p className="muted">{MODES.find((m) => m.id === mode)?.hint}.</p>
              <div className="suggestions">
                {suggestions.map((s) => (
                  <button key={s} className="suggestion" onClick={() => send(s)}>
                    {s} <span aria-hidden>→</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === 'user' ? (
                <div className="bubble">{m.content}</div>
              ) : (
                <div className="answer">
                  {m.fading && m.fading.length > 0 && (
                    <div className="fading-strip">
                      <span className="label">Weaving in</span>
                      {m.fading.slice(0, 3).map((f) => (
                        <Link key={f.id} to={`/concept/${f.id}`} className="fade-chip">
                          {f.name} <StatusWord r={f.retention} />
                        </Link>
                      ))}
                    </div>
                  )}
                  {m.content ? <Md>{m.content}</Md> : <span className="typing" aria-label="Thinking" />}
                  {m.streaming && m.content && <span className="caret" aria-hidden />}
                  {m.sources && m.sources.length > 0 && !m.streaming && (
                    <details className="sources">
                      <summary>
                        {m.sources.length} sources from your library
                      </summary>
                      <ol>
                        {m.sources.map((s) => (
                          <li key={s.chunk_id}>
                            <Link to={`/concept/${s.concept_id}`}>
                              <b>{s.concept_name || s.document_title}</b>
                            </Link>{' '}
                            <span className="muted small">
                              {s.document_title} · p.{s.page + 1} · relevance {pct(s.semantic)} · urgency {pct(s.urgency)}
                            </span>
                            <p className="small">{s.text.length > 220 ? s.text.slice(0, 220) + '…' : s.text}</p>
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                  {!m.streaming && m.content && m.sources && m.sources.length > 0 && (
                    <button className="link-btn small save-btn" onClick={() => saveCards(i)} disabled={m.saved}>
                      <BookmarkPlus size={16} /> {m.saved ? 'Saved as recall questions' : 'Remember this: turn it into recall questions'}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            ref={taRef}
            className="textarea"
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder={mode === 'quiz' ? 'Type “start” or answer the question…' : 'Ask about anything in your library…'}
            aria-label="Message"
          />
          {busy ? (
            <Btn onClick={() => abortRef.current?.abort()} icon={<Square size={18} />} variant="secondary" className="on-ground">
              Stop
            </Btn>
          ) : (
            <Btn type="submit" icon={<Send size={18} />} disabled={!input.trim()}>
              Send
            </Btn>
          )}
        </form>
      </div>
    </div>
  );
}
