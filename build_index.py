import argparse
from datetime import datetime, timezone
import json

from retrieval import ROOT, MODEL, load_embedder, build_vectors, save_index
from trials import TOPICS, fetch_trials, make_chunks


def main():
    parser = argparse.ArgumentParser(description="Build a local RAG index from public neuroscience trial records.")
    parser.add_argument("--topic", choices=[*TOPICS, "All"], default="All")
    parser.add_argument("--limit", type=int, default=10, help="Trials per topic, 1–100")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("Use a limit between 1 and 100.")
    topics = list(TOPICS) if args.topic == "All" else [args.topic]
    trials, raw, versions = [], {}, {}
    for topic in topics:
        print(f"Fetching {topic}...")
        subset, source, version = fetch_trials(topic, args.limit)
        trials.extend(subset)
        raw[topic], versions[topic] = source, version
    unique = {}
    for trial in trials:
        if trial["nct_id"] in unique:
            unique[trial["nct_id"]]["topics"].append(trial["topic"])
        else:
            unique[trial["nct_id"]] = {**trial, "topics": [trial["topic"]]}
    trials = list(unique.values())
    chunks = [chunk for trial in trials for chunk in make_chunks(trial)]
    print(f"Embedding {len(chunks)} passages from {len(trials)} trials on CPU...")
    vectors = build_vectors(load_embedder(), chunks)
    metadata = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "embedding_model": MODEL,
                "api_versions": versions, "topics": topics, "trials_per_topic_requested": args.limit,
                "scope": "Bounded condition searches, sorted by last registry update; protocol sections only."}
    save_index(trials, chunks, vectors, metadata)
    (ROOT / ".local" / "source_snapshot.json").write_text(json.dumps({"metadata": metadata, "studies": raw}))
    print("Index ready. Run: python -m streamlit run app.py")


if __name__ == "__main__":
    main()
