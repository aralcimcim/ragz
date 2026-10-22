"""RAGz: public neuroscience trial evidence explorer."""

import json
import sqlite3

import streamlit as st

from rag import summarize
from retrieval import DB_PATH, filter_trials, load_embedder, load_index, retrieve
from trials import QUESTIONS


st.set_page_config(page_title="RAGz", page_icon="🧠", layout="wide")
st.title("RAGz")
st.write("Explore neuroscience clinical trial protocols with evidence from public registry records.")
st.caption("Research education only. This app does not provide medical advice or determine trial eligibility.")

try:
    trials, chunks, vectors, metadata = load_index()
except (ValueError, sqlite3.Error) as error:
    st.info(str(error))
    st.code("python build_index.py")
    st.stop()

st.caption(f"Local snapshot: {metadata['retrieved_at']} · {len(trials)} trials · {len(chunks)} passages")
with st.expander("About the data and privacy"):
    st.write(
        "This app uses public ClinicalTrials.gov protocol records. It accepts no uploads or personal "
        "health questions. Search and comparisons run locally. The optional Gemini explanation sends "
        "only the retrieved public passages and a preset research question to Google. "
        "This is a small snapshot, not a comprehensive or current review. Results tables are not indexed. "
        "A 'results posted' flag only describes registry metadata."
    )
    st.markdown("[Data source: ClinicalTrials.gov](https://clinicaltrials.gov/)")

left, middle, right = st.columns(3)
topic = left.selectbox("Research topic", metadata["topics"])
topic_trials = filter_trials(trials, topic)
status = middle.selectbox("Registry status", ["All", *sorted({t['status'] for t in topic_trials})])
study_type = right.selectbox("Study type", ["All", *sorted({t['study_type'] for t in topic_trials})])
results_only = st.checkbox("Only records with results posted (results content is not indexed)")
filtered = filter_trials(trials, topic, status, study_type, results_only)
if not filtered:
    st.info("No trials in this snapshot match these filters.")
    st.stop()

by_id = {t["nct_id"]: t for t in filtered}
selected = st.multiselect(
    "Compare up to three trials, or leave empty to search all filtered trials",
    list(by_id), max_selections=3,
    format_func=lambda nct: f"{nct} — {by_id[nct]['title']}",
)
scope = [by_id[nct] for nct in selected] if selected else filtered
st.write(f"{len(filtered)} matching trials · searching {len(scope)} trials")
st.dataframe([
    {"Trial": t["nct_id"], "Title": t["title"], "Status": t["status"],
     "Study type": t["study_type"], "Phase": ", ".join(t["phases"]) or "Not reported",
     "Enrollment": f"{t['enrollment'] if t['enrollment'] is not None else 'Not reported'} ({t['enrollment_type']})",
     "Last update": t["last_updated"], "Source": t["url"]}
    for t in scope
], hide_index=True, column_config={"Source": st.column_config.LinkColumn("Registry record")})

question = st.selectbox("Research question", list(QUESTIONS))
fingerprint = json.dumps([DB_PATH.stat().st_mtime_ns, topic, status, study_type, results_only, selected, question])
if st.session_state.get("search_scope") != fingerprint:
    st.session_state.search_scope = fingerprint
    st.session_state.pop("hits", None)
    st.session_state.pop("answer", None)


@st.cache_resource
def embedder():
    return load_embedder()


if st.button("Find evidence", type="primary"):
    try:
        with st.spinner("Searching local trial passages..."):
            query = next(iter(embedder().query_embed(QUESTIONS[question])))
            st.session_state.hits = retrieve(chunks, vectors, query, {t["nct_id"] for t in scope})
            st.session_state.pop("answer", None)
    except Exception:
        st.error("Could not search the local index. Check the model download and rebuild the index if needed.")

hits = st.session_state.get("hits", [])
if hits:
    st.subheader("Retrieved evidence")
    st.caption("Semantic similarity ranks passages; it does not measure evidence quality or clinical certainty.")
    missing = set(selected) - {h["nct_id"] for h in hits}
    if missing:
        st.info("No passages returned for: " + ", ".join(sorted(missing)))
    for hit in hits:
        with st.expander(f"{hit['nct_id']} · {hit['section']} · similarity {hit['score']:.2f}"):
            st.caption(f"Source ID: {hit['source_id']} · registry updated {hit['last_updated']}")
            st.text(hit["text"])
            st.markdown(f"[Open registry record]({hit['url']})")
    consent = st.checkbox("Send these public passages to Gemini for an optional explanation")
    if st.button("Explain evidence", disabled=not consent):
        try:
            with st.spinner("Preparing a cited explanation..."):
                st.session_state.answer = summarize(question, hits)
        except ValueError as error:
            st.error(str(error))
        except Exception:
            st.error("Gemini could not complete the request. Check your model access, quota, and configuration.")
    if "answer" in st.session_state:
        answer = st.session_state.answer
        st.subheader("Explanation")
        source_lookup = {h["source_id"]: h for h in hits}
        for claim in answer.claims:
            st.write(claim.text)
            for citation in claim.citations:
                st.text(f'“{citation.quote}”')
                source = source_lookup[citation.source_id]
                st.markdown(f"[{citation.source_id}]({source['url']})")
        if not answer.claims:
            st.info("The retrieved passages were insufficient for a supported explanation.")
        st.caption(answer.limitations)
        st.caption("Quotations are checked against retrieved text. This does not verify that every interpretation is correct.")
