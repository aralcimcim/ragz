"""TrialTrace: compose research scopes on an interactive concept canvas."""

import json
import sqlite3

import streamlit as st

from concept_canvas import research_canvas
from rag import summarize
from retrieval import DB_PATH, load_embedder, load_index
from ui import badges, empty_state, section, setup_ui
from workspace import (catalog_for, default_map, map_evidence, question_keys, search_map,
                       selected_concepts, trial_scope, validate_map)


st.set_page_config(page_title="TrialTrace · Research canvas", page_icon="🧠", layout="wide")
setup_ui("#0080FE", "#edf0f9")
st.markdown('''<div class="workspace-nav"><div class="workspace-brand"><span class="brand-symbol" aria-hidden="true">⌘</span>TrialTrace<span class="nav-divider">/</span><span class="nav-subtitle">Research canvas</span></div><span class="nav-status">PUBLIC DATA · LOCAL SEARCH</span></div>
<div class="canvas-intro"><div class="eyebrow">A WORKSPACE FOR CONNECTED THINKING</div><h1>Make connections.<br><span class="muted-heading">Ask better questions.</span></h1><p>Bring topics, questions, and study filters onto one canvas.<br>Combine your ideas. Then follow them back to the evidence.</p></div>''', unsafe_allow_html=True)

try:
    trials, chunks, vectors, metadata = load_index()
except (ValueError, sqlite3.Error) as error:
    st.info(str(error))
    st.code("python build_index.py --topic All")
    st.stop()

st.caption(f"{len(metadata['topics'])} neuroscience topics · {len(trials)} trial records · {len(chunks)} passages · snapshot {metadata['retrieved_at'][:10]} · ClinicalTrials.gov")
catalog = catalog_for(trials, metadata["topics"])
starter = default_map(catalog)
revision = str(DB_PATH.stat().st_mtime_ns)
if st.session_state.get("catalog_revision") != revision:
    st.session_state.catalog_revision = revision
    st.session_state.research_map = starter
    st.session_state.pop("last_canvas_event", None)
    st.session_state.pop("map_search_pending", None)
try:
    state = validate_map(st.session_state.get("research_map", starter), catalog)
except ValueError:
    state = starter
    st.session_state.research_map = state

# Layout changes preserve evidence; concept changes invalidate the old search.
selection_key = json.dumps([DB_PATH.stat().st_mtime_ns, sorted(state["ids"])])
if st.session_state.get("map_selection_key") != selection_key:
    st.session_state.map_selection_key = selection_key
    for key in ("hits", "answer", "explanation_consent", "compare_trials"):
        st.session_state.pop(key, None)

scope = trial_scope(trials, state, catalog)
questions = question_keys(state, catalog)
hits = st.session_state.get("hits", [])
payload = research_canvas(catalog, state, map_evidence(hits), len(scope), starter,
                          st.session_state.get("last_canvas_event"), revision)
if payload and isinstance(payload, dict) and payload.get("event_id") != st.session_state.get("last_canvas_event"):
    event_id = payload.get("event_id")
    if isinstance(event_id, str) and len(event_id) <= 100:
        st.session_state.last_canvas_event = event_id
        try:
            st.session_state.research_map = validate_map(payload, catalog)
            if payload.get("action") == "search":
                st.session_state.map_search_pending = True
            st.rerun()
        except ValueError as error:
            st.error(str(error))

# A native search action also works independently of drag gestures.
can_search = bool(scope and questions)
if not scope:
    st.info("No trials match this map. Add a topic, remove a study filter, or choose a different combination.")
elif not questions:
    st.info("Add at least one question card from the concept library to search the evidence.")

selected = []
with st.expander(f"Matching trials · {len(scope)} records · compare or inspect"):
    by_id = {t["nct_id"]: t for t in scope}
    selected = st.multiselect("Compare specific trials (optional, up to three)", list(by_id),
                              max_selections=3, format_func=lambda nct: f"{nct} — {by_id[nct]['title']}",
                              key="compare_trials", help="Leave empty to search the full map scope.")
    search_clicked = st.button("Find evidence", type="primary", disabled=not can_search,
                               help="Search the current map, restricted to these trials when selected.")
    if scope:
        st.dataframe([
            {"Trial": t["nct_id"], "Study title": t["title"], "Status": t["status"].replace("_", " ").title(),
             "Study type": t["study_type"].title(), "Phase": ", ".join(t["phases"]).replace("PHASE", "Phase ") or "Not reported",
             "Last update": t["last_updated"], "Source": t["url"]} for t in scope
        ], hide_index=True, row_height=44, width="stretch", column_config={
            "Source": st.column_config.LinkColumn("Registry record"),
            "Study title": st.column_config.TextColumn("Study title", width="large"),
        })

comparison_key = json.dumps(sorted(selected))
if st.session_state.get("comparison_key") != comparison_key:
    st.session_state.comparison_key = comparison_key
    for key in ("hits", "answer", "explanation_consent"):
        st.session_state.pop(key, None)
    # Update source nodes when the native comparison scope changes.
    if hits:
        st.rerun()


@st.cache_resource
def embedder():
    return load_embedder()


pending_search = st.session_state.pop("map_search_pending", False)
if search_clicked or pending_search:
    st.session_state.pop("hits", None)
    st.session_state.pop("answer", None)
    if can_search:
        try:
            with st.spinner("Following your concepts into the trial records..."):
                ids = set(selected) if selected else {t["nct_id"] for t in scope}
                st.session_state.hits = search_map(chunks, vectors, ids, questions, embedder())
            st.rerun()
        except (ValueError, RuntimeError) as error:
            st.error(str(error))
        except Exception:
            st.error("Search could not complete. Check the local index and embedding model, then try again.")

hits = st.session_state.get("hits", [])
if hits:
    section("EVIDENCE", "The records behind your map", f"{len(hits)} passages · {len({h['nct_id'] for h in hits})} trials · {len(questions)} research questions")
    st.caption("Open a source node on the map to inspect it, or read the passages below. Search similarity is not evidence quality or clinical certainty.")
    represented = {q for hit in hits for q in hit.get("question_keys", [])}
    missing = set(questions) - represented
    if missing:
        st.info("No passages returned for these question lenses: " + ", ".join(sorted(missing)))
    missing_trials = set(selected) - {h["nct_id"] for h in hits}
    if missing_trials:
        st.info("No passages returned for: " + ", ".join(sorted(missing_trials)))
    for index, hit in enumerate(hits, 1):
        with st.container(border=True, key=f"card_source_{index}"):
            badges([f"SOURCE {index:02}", hit['nct_id'], *hit.get("question_keys", [])])
            st.markdown(f"### {hit['title']}")
            st.caption(f"{hit['section'].title()} · similarity {hit['score']:.2f} · updated {hit['last_updated']}")
            st.text(hit["text"])
            st.markdown(f"[Open original registry record ↗]({hit['url']})")
            st.caption(f"Source ID: {hit['source_id']}")
    section("SYNTHESIS", "Explain the evidence", "An optional, cited explanation across the question cards on your map.")
    consent = st.checkbox("Send these public passages and preset questions to Gemini", key="explanation_consent")
    if st.button("Explain evidence", disabled=not consent):
        try:
            with st.spinner("Preparing a source-backed explanation..."):
                st.session_state.answer = summarize(questions, hits)
        except ValueError as error:
            st.error(str(error))
        except Exception:
            st.error("Gemini could not complete the request. Check model access and quota.")
    if "answer" in st.session_state:
        answer = st.session_state.answer
        source_lookup = {h["source_id"]: h for h in hits}
        for claim in answer.claims:
            st.write(claim.text)
            for citation in claim.citations:
                st.text(f'“{citation.quote}”')
                st.markdown(f"[{citation.source_id}]({source_lookup[citation.source_id]['url']})")
        if not answer.claims:
            st.info("The retrieved passages were insufficient for a supported explanation.")
        st.caption(answer.limitations)
        st.caption("Quotation checks verify text matches, not the correctness of an interpretation.")
elif "hits" in st.session_state:
    st.info("No passages were returned for this map. Try another question or broaden the scope.")
else:
    empty_state("Your map is a starting point", "Add concepts from the library and choose Search this map. Retrieved trial records will connect to your question, with original source passages to inspect.")

with st.expander("How connections, data, and privacy work"):
    st.write("Topic cards combine with OR. Status cards combine with OR, as do study-type cards; those filter categories narrow the selected topics with AND. Each question card gets its own local search, and results are interleaved with at most two passages per trial. The map shows up to three retrieved trial nodes; all retrieved passages appear below it.")
    st.write("Connections represent your search scope and retrieved records. They do not assert biological relationships, causation, or scientific agreement. The dataset is a limited public registry snapshot, not a systematic review. Protocols describe plans; results tables are not indexed.")
    st.write("No patient uploads or personal health questions are accepted. Map contents stay in the session unless you choose Save map, which downloads a local JSON file. Only an explicit explanation request sends retrieved public passages and preset questions to Gemini.")
    st.markdown("[ClinicalTrials.gov](https://clinicaltrials.gov/)")
st.divider()
st.caption("TrialTrace / Research canvas · Research education only · Not medical advice or a personal eligibility assessment.")
