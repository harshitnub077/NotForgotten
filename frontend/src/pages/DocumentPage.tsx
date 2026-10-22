import { Link, useParams } from 'react-router-dom';
import { FileText } from 'lucide-react';
import { api } from '../api';
import { Btn, ErrorBox, Flap, RecallBar, SignBand, Skeleton, StatusWord, pct, useLoad } from '../ui';

export default function DocumentPage() {
  const { id = '' } = useParams();
  const { data, error, reload } = useLoad(() => api.document(id), [id]);

  if (error) return <div className="page"><ErrorBox error={error} onRetry={() => reload()} /></div>;
  if (!data)
    return (
      <div className="page">
        <Skeleton h={140} />
        <Skeleton h={300} />
      </div>
    );

  const concepts = data.concepts ?? [];
  const learned = concepts.filter((c) => c.retention != null);
  const avg = learned.length ? learned.reduce((s, c) => s + (c.retention ?? 0), 0) / learned.length : null;

  return (
    <>
      <SignBand
        icon={<FileText size={44} />}
        title={data.title}
        sub={`${data.concept_count} concepts · ${data.card_count} cards · ${avg == null ? 'not studied yet' : `average recall ${pct(avg)}`}`}
        actions={
          <Btn to={`/review?document=${data.id}`} size="big">
            Study this source
          </Btn>
        }
      />
      <div className="page">
        <p className="small">
          <Link to="/library">← Library</Link>
        </p>
        <section className="board">
          <div className="board-head">
            <h2>Concepts in reading order</h2>
          </div>
          <div className="board-cols" style={{ ['--board-cols' as string]: '64px 1fr 80px 112px 92px' }}>
            <span>Recall</span>
            <span>Concept</span>
            <span className="hide-sm">Cards</span>
            <span>Status</span>
            <span className="hide-sm">Strength</span>
          </div>
          {concepts.map((c) => (
            <Link key={c.id} to={`/concept/${c.id}`} className="board-row" style={{ ['--board-cols' as string]: '64px 1fr 80px 112px 92px' }}>
              <Flap text={pct(c.retention).padStart(4)} />
              <span style={{ minWidth: 0 }}>
                <span className="name" style={{ display: 'block' }}>
                  {c.name}
                </span>
                <span className="sub" style={{ display: 'block' }}>
                  {c.summary}
                </span>
              </span>
              <span className="hide-sm">
                {c.learned}/{c.cards}
              </span>
              <StatusWord r={c.retention} />
              <span className="hide-sm">
                <RecallBar r={c.retention} />
              </span>
            </Link>
          ))}
        </section>
      </div>
    </>
  );
}
