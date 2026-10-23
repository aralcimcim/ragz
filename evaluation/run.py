"""Evaluate top-five evidence retrieval on the committed, labelled snapshot.

No generation API is called. First run may download the local embedding model.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent


def load_cases(corpus, source_key):
    cases = json.loads((HERE / "questions.json").read_text())
    seen = set()
    for case in cases:
        if case["id"] in seen or not case["relevant_sources"]:
            raise ValueError("Duplicate case ID or missing labels")
        seen.add(case["id"])
        sources = {source_key(r): r["text"] for r in corpus(case)}
        for label in case["relevant_sources"]:
            if not label["quote"].strip() or label["quote"] not in sources.get(label["source_id"], ""):
                raise ValueError("Label does not match corpus: " + case["id"])
    return cases


def score(case, hits, mode, source_key):
    expected = {r["source_id"] for r in case["relevant_sources"]}
    ids = [source_key(r) for r in hits[:5]]
    rank = next((i for i, sid in enumerate(ids, 1) if sid in expected), None)
    return {"id": case["id"], "task": case.get("task", "trial_question"),
            "mode": mode, "question": case["question"],
            "support_in_top_5": rank is not None, "first_support_rank": rank,
            "expected_source_ids": sorted(expected), "retrieved_source_ids": ids}


def report(rows, model, corpus_counts, settings):
    groups = {}
    for row in rows:
        key = row["task"] + " / " + row["mode"]
        groups.setdefault(key, []).append(row)
    summary = {}
    for key, values in groups.items():
        hits = sum(v["support_in_top_5"] for v in values)
        summary[key] = {"questions": len(values), "hits": hits, "hit_at_5": hits / len(values)}
        print(f"{key}: {hits}/{len(values)} supporting passage in top five ({hits/len(values):.1%})")
    result = {"metric": "Hit@5: fraction of questions with at least one labelled supporting passage in the first five results",
              "embedding_model": model, "fastembed_version": importlib.metadata.version("fastembed"),
              "corpus_sha256": hashlib.sha256((HERE / "corpus.json").read_bytes()).hexdigest(),
              "questions_sha256": hashlib.sha256((HERE / "questions.json").read_bytes()).hexdigest(),
              "corpus_counts": corpus_counts, "settings": settings,
              "summary": summary, "cases": rows}
    (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Per-question results written to evaluation/results.json")


def main():
    from retrieval import MODEL, build_vectors, load_embedder, retrieve

    data = json.loads((HERE / "corpus.json").read_text())
    chunks = data["chunks"]
    cases = load_cases(lambda _: chunks, lambda r: r["source_id"])
    embedder = load_embedder()
    vectors = build_vectors(embedder, chunks)
    queries = list(embedder.query_embed([c["question"] for c in cases]))
    trial_ids = {t["nct_id"] for t in data["trials"]}
    rows = [score(case, retrieve(chunks, vectors, query, trial_ids, top_k=5),
                  "Semantic", lambda r: r["source_id"]) for case, query in zip(cases, queries)]
    report(rows, MODEL, {"trials": len(trial_ids), "passages": len(chunks)},
           {"top_k": 5, "scope": "All frozen trials, no filters", "max_passages_per_trial": 2})


if __name__ == "__main__":
    main()
