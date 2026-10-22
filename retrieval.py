"""A bounded SQLite vector store and local semantic retrieval."""

import json
from pathlib import Path
import sqlite3

import numpy as np


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / ".local" / "trials.sqlite3"
MODEL = "BAAI/bge-small-en-v1.5"


def load_embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODEL, cache_dir=str(ROOT / ".local" / "models"), threads=2)


def build_vectors(embedder, chunks):
    vectors = np.asarray(list(embedder.passage_embed([chunk["text"] for chunk in chunks])), dtype=np.float32)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)


def save_index(trials, chunks, vectors, metadata, path=DB_PATH):
    if not chunks or len(chunks) != len(vectors) or vectors.ndim != 2 or not np.isfinite(vectors).all():
        raise ValueError("Each evidence passage must have one finite embedding.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS trials (id TEXT PRIMARY KEY, data TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, data TEXT, vector BLOB)")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("DELETE FROM trials")
        db.execute("DELETE FROM chunks")
        db.execute("DELETE FROM metadata")
        db.executemany("INSERT INTO trials VALUES (?, ?)", [(t["nct_id"], json.dumps(t)) for t in trials])
        db.executemany("INSERT INTO chunks VALUES (?, ?, ?)", [
            (c["source_id"], json.dumps(c), np.asarray(v, dtype=np.float32).tobytes()) for c, v in zip(chunks, vectors)
        ])
        db.executemany("INSERT INTO metadata VALUES (?, ?)", [(k, json.dumps(v)) for k, v in metadata.items()])


def load_index(path=DB_PATH):
    if not path.exists():
        raise ValueError("Download and index public trials first: python build_index.py")
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        trials = [json.loads(row[0]) for row in db.execute("SELECT data FROM trials ORDER BY id")]
        rows = db.execute("SELECT data, vector FROM chunks ORDER BY id").fetchall()
        metadata = {k: json.loads(v) for k, v in db.execute("SELECT key, value FROM metadata")}
    if not rows:
        raise ValueError("The trial index is empty. Rebuild it.")
    return trials, [json.loads(row[0]) for row in rows], np.stack([
        np.frombuffer(row[1], dtype=np.float32) for row in rows
    ]), metadata


def filter_trials(trials, topic, status="All", study_type="All", results_only=False):
    return [t for t in trials if topic in t.get("topics", [t["topic"]])
            and (status == "All" or t["status"] == status)
            and (study_type == "All" or t["study_type"] == study_type)
            and (not results_only or t["has_results"])]


def retrieve(chunks, vectors, query, trial_ids, top_k=8):
    query = np.asarray(query, dtype=np.float32)
    norm = float(np.linalg.norm(query))
    if not np.isfinite(query).all() or norm == 0:
        raise ValueError("The query embedding is invalid.")
    scores = vectors @ (query / norm)
    eligible = [i for i, chunk in enumerate(chunks) if chunk["nct_id"] in trial_ids]
    ranked = sorted(eligible, key=lambda i: (-scores[i], chunks[i]["source_id"]))
    counts, hits = {}, []
    # Cap each trial at two passages so a single long record cannot dominate.
    for i in ranked:
        nct = chunks[i]["nct_id"]
        if counts.get(nct, 0) >= 2:
            continue
        hits.append({**chunks[i], "score": float(scores[i])})
        counts[nct] = counts.get(nct, 0) + 1
        if len(hits) == top_k:
            break
    return hits
