# TrialTrace

A visual research workspace for exploring public neuroscience clinical trial protocols with local semantic search and optional cited Gemini explanations.

Compose a research map from topics, question cards, and study filters. Retrieved trial records connect back to the map, with source passages available in an evidence drawer. No patient uploads or personal health questions are accepted.

## Use the research canvas

1. Drag cards from **Topics**, **Questions**, or **Filters** onto the canvas. Clicking or keyboard-activating a library card also adds it.
2. Move cards to organize your thinking. Connected concepts change the research scope or the questions being searched; moving a card preserves the search.
3. Select **Search this map**. Each question gets its own semantic search. Evidence is interleaved into a combined set of up to eight passages, with at most two per trial.
4. Open **Read evidence** on a source node to inspect its passages and registry link. The map shows the first three retrieved trials; all passages remain available below it.
5. Use **Undo**, **Arrange**, **Reset**, or **Clear** to edit the map. **Save map** downloads a local JSON description; it is an export, not an automatic saved account or an import feature.

Topics combine with **OR**. Statuses combine with OR, and study types combine with OR; those filter categories narrow the topic set with **AND**. The **Results posted** card filters only the registry flag; results tables are not indexed. No filter cards means all statuses and types. You can connect up to eight concepts.

Use **List** for a compact, keyboard-friendly view, which is the default on small screens. Canvas nodes support arrow keys to move and Delete/Backspace to remove. The trial comparison controls below the map can restrict retrieval to up to three records.

Connections represent the search you composed and records actually retrieved. They do not assert biological relationships, causation, scientific agreement, or evidence quality. Changing concepts clears previous evidence and explanations; layout-only changes preserve them. Maps are session-local unless explicitly exported.

The canvas is a [local Streamlit component](https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro) built with HTML, CSS, JavaScript, and SVG. No npm build, external graph library, font service, or CDN is required. The academic serif is locally hosted STIX Two Text; its license is included in `fonts/OFL.txt`. Dark blue is the primary accent.

## Run locally

```bash
git clone https://github.com/aralcimcim/ragz.git
cd ragz
conda env create -f environment.yml
conda activate trialtrace
python -m pip install -r requirements.txt
python build_index.py
python -m streamlit run app.py --server.port 8503
```

Open the local URL printed by Streamlit. The default index contains up to 10 recently updated records per topic across 13 neuroscience topics. To request a larger snapshot:

```bash
python build_index.py --topic All --limit 20
```

Topics include Alzheimer's disease, Parkinson's disease, mild cognitive impairment, epilepsy, multiple sclerosis, stroke, traumatic brain injury, ALS, Huntington's disease, migraine, sleep disorders, ADHD, and autism spectrum disorder. They are registry search categories, not diagnoses or clinical advice.

Each build replaces the previous index. The first build downloads a small embedding model, runs it on CPU, and saves public source records, model files, and an SQLite vector index under `.local/`. No GPU, Azure subscription, or language model API key is needed for search and comparisons.

## Use with Gemini

```bash
cp .env.example .env
```

Set your own `GEMINI_API_KEY` and an available `GEMINI_MODEL` in `.env`. Search your map, then opt in to sending the public passages and preset question cards to Gemini and select **Explain evidence**. API usage may cost money according to your account. Keep `.env` out of Git; it is ignored.

Each generated claim must cite a retrieved source ID and an exact supporting quotation. Unknown sources and mismatched quotations reject the response. Matching quotations do not guarantee that the model's interpretation is correct.

## How it works

1. Download public records from the [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api).
2. Split protocol fields into overlapping passages and embed them with `BAAI/bge-small-en-v1.5` through FastEmbed.
3. Store records and vectors in SQLite. Filter records, then rank passages by cosine similarity, with at most two passages per trial.
4. Optionally send retrieved passages to Gemini for a structured, cited explanation.

The source snapshot records retrieval time and API version information. Registry links and last-update dates accompany the evidence. Rebuild to refresh it.
