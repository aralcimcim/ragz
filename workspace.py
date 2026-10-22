"""Validate visual research maps and translate them into real retrieval scopes."""

from collections import Counter
import math

from retrieval import retrieve
from trials import QUESTIONS


def catalog_for(trials, topics):
    concepts = []
    for i, topic in enumerate(topics):
        count = sum(topic in t.get("topics", [t["topic"]]) for t in trials)
        concepts.append(dict(id=f"topic:{i}", kind="topic", label=topic, value=topic,
                             detail=f"{count} trial records", count=count))
    for i, (label, question) in enumerate(QUESTIONS.items()):
        concepts.append(dict(id=f"question:{i}", kind="question", label=label, value=label, detail=question))
    for field, kind in [("status", "status"), ("study_type", "type")]:
        for i, (value, count) in enumerate(sorted(Counter(t[field] for t in trials).items())):
            concepts.append(dict(id=f"{kind}:{i}", kind=kind, value=value,
                                 label=value.replace("_", " ").title(), detail=f"{count} trial records", count=count))
    concepts.append(dict(id="availability:results", kind="availability", value="results_posted",
                         label="Results posted", detail="Registry flag only; result tables are not indexed",
                         count=sum(t.get("has_results", False) for t in trials)))
    return concepts


def default_map(catalog):
    topic = next(c["id"] for c in catalog if c["kind"] == "topic")
    question = next(c["id"] for c in catalog if c["kind"] == "question")
    return {"ids": [topic, question], "positions": {topic: {"x": 65, "y": 105}, question: {"x": 65, "y": 355}}}


def validate_map(value, catalog):
    if not isinstance(value, dict) or not isinstance(value.get("ids"), list):
        raise ValueError("Invalid research map.")
    allowed = {c["id"] for c in catalog}
    ids = value["ids"]
    if len(ids) > 8 or any(not isinstance(i, str) or i not in allowed for i in ids):
        raise ValueError("Choose concepts from the research library.")
    if len(ids) != len(set(ids)):
        raise ValueError("A concept may only appear once on the map.")
    positions = {}
    supplied = value.get("positions", {})
    if not isinstance(supplied, dict):
        raise ValueError("Invalid concept positions.")
    for node in ids:
        p = supplied.get(node, {"x": 50, "y": 50})
        if not isinstance(p, dict):
            raise ValueError("Invalid concept position.")
        x, y = p.get("x", 50), p.get("y", 50)
        if not all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in (x, y)):
            raise ValueError("Invalid concept position.")
        positions[node] = {"x": min(680, max(10, x)), "y": min(440, max(10, y))}
    return {"ids": ids, "positions": positions}


def selected_concepts(state, catalog, kind):
    selected = set(state["ids"])
    return [c for c in catalog if c["id"] in selected and c["kind"] == kind]


def trial_scope(trials, state, catalog):
    topics = {c["value"] for c in selected_concepts(state, catalog, "topic")}
    statuses = {c["value"] for c in selected_concepts(state, catalog, "status")}
    types = {c["value"] for c in selected_concepts(state, catalog, "type")}
    results_only = bool(selected_concepts(state, catalog, "availability"))
    return [t for t in trials if topics.intersection(t.get("topics", [t["topic"]]))
            and (not statuses or t["status"] in statuses)
            and (not types or t["study_type"] in types)
            and (not results_only or t.get("has_results", False))]


def question_keys(state, catalog):
    return [c["value"] for c in selected_concepts(state, catalog, "question")]


def search_map(chunks, vectors, trial_ids, questions, embedder, top_k=8):
    """Search each question independently, then interleave its ranked evidence."""
    if not trial_ids or not questions or any(q not in QUESTIONS for q in questions):
        raise ValueError("Add a topic and question with matching trials before searching.")
    ranked = []
    for question in questions:
        query = next(iter(embedder.query_embed(QUESTIONS[question])))
        ranked.append(retrieve(chunks, vectors, query, trial_ids, top_k=top_k))
    hits, seen, counts = [], {}, Counter()
    for rank in range(max(map(len, ranked), default=0)):
        for question, group in zip(questions, ranked):
            if rank >= len(group):
                continue
            hit = group[rank]
            if hit["source_id"] in seen:
                if question not in seen[hit["source_id"]]["question_keys"]:
                    seen[hit["source_id"]]["question_keys"].append(question)
                continue
            if len(hits) >= top_k or counts[hit["nct_id"]] >= 2:
                continue
            item = {**hit, "question_keys": [question]}
            hits.append(item)
            seen[hit["source_id"]] = item
            counts[hit["nct_id"]] += 1
    return hits


def map_evidence(hits):
    records = {}
    for hit in hits:
        record = records.setdefault(hit["nct_id"], {"id": hit["nct_id"], "title": hit["title"],
                                                   "url": hit["url"], "passages": []})
        record["passages"].append({"section": hit["section"], "text": hit["text"], "source_id": hit["source_id"]})
    return list(records.values())
