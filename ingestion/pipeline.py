"""
Ingestion pipeline, run as a background job with live progress.

    extract → chunk → embed → discover concepts → name → generate cards → link graph

Jobs run one at a time on a single worker thread (SQLite writes and LLM rate
limits both prefer serial work); card generation fans out to a small pool.
"""
from __future__ import annotations

import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import numpy as np

from core import settings
from core.util import iso, jdumps, jloads, new_id, utcnow
from ingestion.chunker import chunk_pages
from ingestion.extract import Extracted, extract_pdf, extract_text, extract_url
from memory.schema import get_conn, init_db
from nlp.cards import generate_cards
from nlp.concepts import ConceptNode, build_edges, discover_concepts, refine_with_llm

_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
_CARD_WORKERS = 3


# ---------------------------------------------------------------------------
# Job bookkeeping
# ---------------------------------------------------------------------------


def _job_update(job_id: str, stage: str, progress: float, message: str, status: str = "running") -> None:
    now = iso(utcnow())
    with get_conn() as conn:
        row = conn.execute("SELECT log FROM jobs WHERE id = ?", (job_id,)).fetchone()
        log = jloads(row["log"], []) if row else []
        log.append({"t": now, "stage": stage, "message": message})
        conn.execute(
            "UPDATE jobs SET stage = ?, progress = ?, message = ?, status = ?, log = ?, updated_at = ? WHERE id = ?",
            (stage, round(progress, 3), message, status, jdumps(log[-40:]), now, job_id),
        )


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = dict(row)
    job["log"] = jloads(job["log"], [])
    return job


def list_active_jobs() -> List[Dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE status = 'running' ORDER BY created_at DESC"
        ).fetchall()
    return [j for j in (get_job(r["id"]) for r in rows) if j]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def submit(source: Dict[str, Any], sync: bool = False, is_demo: bool = False) -> Dict[str, str]:
    """
    *source* is one of
        {"kind": "pdf", "path": str, "filename": str}
        {"kind": "text" | "markdown", "text": str, "title": str}
        {"kind": "url", "url": str}
    """
    init_db()
    now = iso(utcnow())
    doc_id, job_id = new_id("doc"), new_id("job")
    title = source.get("title") or source.get("filename") or source.get("url") or "Untitled"
    size = len(source.get("text", "")) or (
        os.path.getsize(source["path"]) if source.get("path") and os.path.exists(source["path"]) else 0
    )
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO documents (id, title, filename, kind, source_url, size_bytes, status, is_demo, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'processing', ?, ?)""",
            (doc_id, title[:200], source.get("filename"), source["kind"], source.get("url"), size, int(is_demo), now),
        )
        conn.execute(
            "INSERT INTO jobs (id, document_id, status, stage, progress, message, created_at, updated_at) "
            "VALUES (?, ?, 'running', 'queued', 0, 'Waiting to start…', ?, ?)",
            (job_id, doc_id, now, now),
        )
    if sync:
        _run(job_id, doc_id, source)
    else:
        _worker.submit(_run, job_id, doc_id, source)
    return {"job_id": job_id, "document_id": doc_id}


def _extract(source: Dict[str, Any]) -> Extracted:
    kind = source["kind"]
    if kind == "pdf":
        name = source.get("filename") or "document.pdf"
        return extract_pdf(source["path"], os.path.splitext(name)[0])
    if kind in ("text", "markdown"):
        return extract_text(source["text"], source.get("title") or "Notes")
    if kind == "url":
        return extract_url(source["url"])
    raise ValueError(f"Unknown source kind: {kind}")


def _run(job_id: str, doc_id: str, source: Dict[str, Any]) -> None:
    try:
        _ingest(job_id, doc_id, source)
    except Exception as exc:  # noqa: BLE001 — report any failure to the user
        traceback.print_exc()
        msg = str(exc) or type(exc).__name__
        with get_conn() as conn:
            conn.execute("UPDATE documents SET status = 'failed', error = ? WHERE id = ?", (msg[:500], doc_id))
        _job_update(job_id, "failed", 1.0, msg[:300], status="failed")
    finally:
        if source.get("kind") == "pdf" and source.get("cleanup") and os.path.exists(source["path"]):
            os.remove(source["path"])


def _ingest(job_id: str, doc_id: str, source: Dict[str, Any]) -> None:
    from ingestion.embedder import embed_texts
    from retrieval.vector_store import get_store

    use_llm = bool(settings.get("use_llm"))

    _job_update(job_id, "extracting", 0.05, "Reading the source…")
    extracted = _extract(source)
    with get_conn() as conn:
        conn.execute("UPDATE documents SET title = ? WHERE id = ?", (extracted.title[:200], doc_id))

    _job_update(job_id, "chunking", 0.12, f"Splitting {len(extracted.pages)} sections into passages…")
    chunks = chunk_pages(extracted.pages)
    if not chunks:
        raise ValueError("No readable text found.")
    texts = [c.text for c in chunks]

    _job_update(job_id, "embedding", 0.2, f"Embedding {len(chunks)} passages into semantic space…")
    vectors = embed_texts(texts)

    _job_update(job_id, "concepts", 0.38, "Discovering concepts with clustering…")
    drafts = discover_concepts(texts, vectors, sections=[c.page for c in chunks], headed=extracted.headed)
    if use_llm and refine_with_llm(drafts, texts):
        _job_update(job_id, "naming", 0.45, f"Named {len(drafts)} concepts with AI.")
    else:
        _job_update(job_id, "naming", 0.45, f"Found {len(drafts)} concepts.")

    now = iso(utcnow())
    chunk_ids = [f"{doc_id}_c{c.idx}" for c in chunks]
    concept_ids = [new_id("con") for _ in drafts]
    chunk_concept: Dict[int, str] = {}
    for cid, d in zip(concept_ids, drafts):
        for i in d.chunk_indices:
            chunk_concept[i] = cid

    with get_conn() as conn:
        for cid, d in zip(concept_ids, drafts):
            conn.execute(
                """INSERT INTO concepts (id, document_id, name, summary, keywords, centroid, position, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    doc_id,
                    d.name,
                    d.summary,
                    jdumps(d.keywords),
                    jdumps([round(float(x), 5) for x in d.centroid]),
                    d.position,
                    now,
                ),
            )
        conn.executemany(
            "INSERT INTO chunks (id, document_id, idx, page, text, concept_id) VALUES (?, ?, ?, ?, ?, ?)",
            [(chunk_ids[c.idx], doc_id, c.idx, c.page, c.text, chunk_concept.get(c.idx)) for c in chunks],
        )

    _job_update(job_id, "indexing", 0.5, "Indexing passages for semantic search…")
    get_store().add(
        chunk_ids,
        vectors.tolist(),
        texts,
        [
            {"document_id": doc_id, "concept_id": chunk_concept.get(c.idx, ""), "page": c.page, "idx": c.idx}
            for c in chunks
        ],
    )

    # ── Cards ─────────────────────────────────────────────────────────────
    total = len(drafts)
    done = [0]

    def make_cards(pair):
        cid, d = pair
        sims = sorted(d.chunk_indices, key=lambda i: -float(np.dot(vectors[i], d.centroid)))
        central = sorted(sims[:4])
        excerpts = [texts[i] for i in central]
        n = max(3, min(7, 2 + len(d.chunk_indices) // 2))
        cards = generate_cards(d.name, d.summary, d.keywords, excerpts, n_cards=n, use_llm=use_llm)
        done[0] += 1
        _job_update(
            job_id,
            "cards",
            0.55 + 0.37 * done[0] / max(total, 1),
            f"Writing recall questions — concept {done[0]}/{total}: {d.name}",
        )
        return cid, central, cards

    card_rows = []
    with ThreadPoolExecutor(max_workers=_CARD_WORKERS if use_llm else 1) as pool:
        for cid, central, cards in pool.map(make_cards, zip(concept_ids, drafts)):
            for card in cards:
                src = central[card.source_index] if card.source_index is not None and card.source_index < len(central) else (central[0] if central else None)
                card_rows.append(
                    (
                        new_id("card"),
                        cid,
                        doc_id,
                        card.kind,
                        card.prompt,
                        card.answer,
                        card.explanation,
                        chunk_ids[src] if src is not None else None,
                        "generated",
                        now,
                    )
                )
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO cards (id, concept_id, document_id, kind, prompt, answer, explanation,
                   source_chunk_id, origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            card_rows,
        )

    _job_update(job_id, "linking", 0.95, "Linking concepts into your knowledge graph…")
    n_links = rebuild_links()

    with get_conn() as conn:
        conn.execute(
            """UPDATE documents SET status = 'ready', chunk_count = ?, concept_count = ?, card_count = ?
               WHERE id = ?""",
            (len(chunks), len(drafts), len(card_rows), doc_id),
        )
    _job_update(
        job_id,
        "done",
        1.0,
        f"Ready — {len(drafts)} concepts, {len(card_rows)} cards, {n_links} graph links.",
        status="done",
    )


def rebuild_links() -> int:
    """Recompute concept edges across the whole library."""
    with get_conn() as conn:
        rows = conn.execute("SELECT id, document_id, position, centroid FROM concepts").fetchall()
        nodes = [
            ConceptNode(r["id"], r["document_id"], r["position"], np.array(jloads(r["centroid"], []), dtype=np.float32))
            for r in rows
            if jloads(r["centroid"], [])
        ]
        edges = build_edges(nodes)
        conn.execute("DELETE FROM concept_links")
        conn.executemany(
            "INSERT OR REPLACE INTO concept_links (source, target, weight, kind) VALUES (?, ?, ?, ?)",
            edges,
        )
    return len(edges)


def delete_document(doc_id: str) -> bool:
    from retrieval.vector_store import get_store

    with get_conn() as conn:
        cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        if cur.rowcount == 0:
            return False
    try:
        get_store().delete_document(doc_id)
    except Exception:  # noqa: BLE001 — vector cleanup is best-effort
        traceback.print_exc()
    rebuild_links()
    return True
