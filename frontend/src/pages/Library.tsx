import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, FileText, Globe, Search, Trash2, UploadCloud, Type } from 'lucide-react';
import { api, type Doc, type Job, type SearchHit } from '../api';
import { Btn, ErrorBox, Flap, Picto, SignBand, Skeleton, useLoad, useToast } from '../ui';

type Tab = 'file' | 'text' | 'url';

function JobBoard({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return null;
  return (
    <section className="board" aria-live="polite" aria-label="Processing">
      <div className="board-head">
        <h2>Now processing</h2>
      </div>
      {jobs.map((j) => (
        <div key={j.id} className="job-row">
          <div className="job-top">
            <Flap text={j.stage.toUpperCase()} className={`status ${j.status === 'failed' ? 'rebook' : j.status === 'done' ? 'ontime' : 'boarding'}`} />
            <span className="mono small" style={{ color: 'var(--board-dim)' }}>
              {Math.round(j.progress * 100)}%
            </span>
          </div>
          <div className="job-msg">{j.message}</div>
          <div className="job-bar">
            <i style={{ width: `${Math.max(3, j.progress * 100)}%` }} />
          </div>
        </div>
      ))}
    </section>
  );
}

function AddPanel({ onQueued }: { onQueued: (jobId: string) => void }) {
  const [tab, setTab] = useState<Tab>('file');
  const [drag, setDrag] = useState(false);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const run = async (fn: () => Promise<{ job_id: string }>) => {
    setError(null);
    setBusy(true);
    try {
      const { job_id } = await fn();
      onQueued(job_id);
      setText('');
      setTitle('');
      setUrl('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((f) => run(() => api.upload(f)));
  };

  return (
    <section className="surface add-panel" aria-label="Add study material">
      <div className="add-tabs" role="tablist">
        {(
          [
            ['file', 'Upload a file', UploadCloud],
            ['text', 'Paste notes', Type],
            ['url', 'From a web page', Globe],
          ] as const
        ).map(([key, label, Icon]) => (
          <button key={key} role="tab" aria-selected={tab === key} className="add-tab" onClick={() => setTab(key)}>
            <Icon size={18} /> {label}
          </button>
        ))}
      </div>
      <div className="panel-body">
        {tab === 'file' && (
          <div
            className={`dropzone${drag ? ' over' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              onFiles(e.dataTransfer.files);
            }}
            onClick={() => fileRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileRef.current?.click()}
          >
            <Picto size="lg">
              <UploadCloud size={40} />
            </Picto>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.35rem' }}>Drop lecture PDFs, notes or chapters</div>
              <div className="muted">PDF, TXT or Markdown, up to 60 MB · or click to choose</div>
            </div>
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.markdown" multiple hidden onChange={(e) => onFiles(e.target.files)} />
          </div>
        )}
        {tab === 'text' && (
          <form
            className="field-stack"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => api.addText(title || 'My notes', text));
            }}
          >
            <div className="field">
              <label className="label" htmlFor="t-title">
                Title
              </label>
              <input id="t-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Organic chemistry — week 3" />
            </div>
            <div className="field">
              <label className="label" htmlFor="t-text">
                Notes
              </label>
              <textarea
                id="t-text"
                className="textarea"
                style={{ minHeight: 200 }}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste lecture notes, a chapter or a summary. Markdown headings become concepts."
              />
            </div>
            <div>
              <Btn type="submit" disabled={busy || text.trim().length < 40}>
                Turn into recall questions
              </Btn>
            </div>
          </form>
        )}
        {tab === 'url' && (
          <form
            className="field-stack"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => api.addUrl(url.trim()));
            }}
          >
            <div className="field">
              <label className="label" htmlFor="t-url">
                Article or page address
              </label>
              <input id="t-url" className="input" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://en.wikipedia.org/wiki/Krebs_cycle" />
            </div>
            <div>
              <Btn type="submit" disabled={busy || !/^https?:\/\//.test(url.trim())}>
                Import page
              </Btn>
            </div>
          </form>
        )}
        {error && (
          <div style={{ marginTop: 14 }}>
            <ErrorBox error={error} />
          </div>
        )}
      </div>
    </section>
  );
}

function SearchPanel() {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    try {
      setHits(await api.search(q));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="surface">
      <div className="panel-head">
        <h2>Search by meaning</h2>
      </div>
      <div className="panel-body field-stack">
        <form onSubmit={run} style={{ display: 'flex', gap: 10 }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask in your own words, e.g. “why does cramming fail”" aria-label="Search your library" />
          <Btn type="submit" icon={<Search size={20} />} disabled={busy}>
            Search
          </Btn>
        </form>
        <p className="small muted">Results blend relevance with how much you're forgetting each concept, so fading material surfaces first.</p>
        {hits && hits.length === 0 && <p className="muted">Nothing matched yet.</p>}
        {hits?.map((h) => (
          <Link key={h.chunk_id} to={`/concept/${h.concept_id}`} className="hit">
            <div className="hit-head">
              <b>{h.concept_name}</b>
              <span className="muted small">{h.document_title} · p.{h.page + 1}</span>
              <span className="spacer mono small" title="relevance · forgetting urgency">
                {Math.round(h.semantic * 100)} · {Math.round(h.urgency * 100)}
              </span>
            </div>
            <p className="hit-text">{h.text.length > 280 ? h.text.slice(0, 280) + '…' : h.text}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function Library() {
  const docs = useLoad(() => api.documents());
  const [jobs, setJobs] = useState<Job[]>([]);
  const prevJobs = useRef<Job[]>([]);
  const toast = useToast();
  const reloadDocs = docs.reload;

  const pollJobs = useCallback(async () => {
    const active = await api.jobs().catch(() => [] as Job[]);
    const finished = prevJobs.current.filter((p) => !active.find((a) => a.id === p.id));
    prevJobs.current = active;
    setJobs(active);
    if (finished.length || active.length) reloadDocs(true);
    for (const f of finished) {
      const j = await api.job(f.id).catch(() => null);
      if (j) toast(j.status === 'done' ? j.message : `Import failed: ${j.message}`);
    }
  }, [reloadDocs, toast]);

  useEffect(() => {
    pollJobs();
    const id = window.setInterval(pollJobs, 1200);
    return () => window.clearInterval(id);
  }, [pollJobs]);

  const remove = async (d: Doc) => {
    if (!window.confirm(`Remove “${d.title}”? Its concepts, cards and review history will be deleted.`)) return;
    await api.deleteDocument(d.id);
    docs.reload(true);
  };

  return (
    <>
      <SignBand
        icon={<BookOpen size={44} />}
        title="Library"
        sub="Everything you're learning. Each source is split into concepts, and each concept gets its own recall questions."
      />
      <div className="page">
        <div className="lib-grid">
          <div className="field-stack" style={{ gap: 20 }}>
            <AddPanel onQueued={() => pollJobs()} />
            <JobBoard jobs={jobs} />
          </div>
          <SearchPanel />
        </div>

        <section className="surface">
          <div className="panel-head">
            <h2>Sources</h2>
            <span className="spacer muted small">{docs.data?.length ?? 0} total</span>
          </div>
          {docs.loading && !docs.data && (
            <div className="panel-body">
              <Skeleton h={120} />
            </div>
          )}
          {docs.error && (
            <div className="panel-body">
              <ErrorBox error={docs.error} onRetry={() => docs.reload()} />
            </div>
          )}
          {docs.data && docs.data.length === 0 && <div className="panel-body muted">No sources yet. Add your first one above.</div>}
          <div className="doc-list">
            {docs.data?.map((d) => (
              <div key={d.id} className="doc-row">
                <Picto size="sm">{d.kind === 'url' ? <Globe size={18} /> : <FileText size={18} />}</Picto>
                <Link to={`/library/${d.id}`} className="doc-title">
                  <b>{d.title}</b>
                  <span className="muted small">
                    {d.kind.toUpperCase()} · added {new Date(d.created_at).toLocaleDateString()}
                    {d.is_demo ? ' · demo' : ''}
                  </span>
                </Link>
                <span className="doc-stat">
                  <b>{d.concept_count}</b> concepts
                </span>
                <span className="doc-stat">
                  <b>{d.card_count}</b> cards
                </span>
                <span className={`status chip ${d.status === 'ready' ? 'ontime' : d.status === 'failed' ? 'rebook' : 'boarding'}`} title={d.error ?? undefined}>
                  {d.status === 'ready' ? 'READY' : d.status === 'failed' ? 'FAILED' : 'PROCESSING'}
                </span>
                <span className="doc-actions">
                  {d.status === 'ready' && (
                    <Btn size="sm" to={`/review?document=${d.id}`}>
                      Study
                    </Btn>
                  )}
                  <button className="icon-btn" aria-label={`Remove ${d.title}`} onClick={() => remove(d)}>
                    <Trash2 size={18} />
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
