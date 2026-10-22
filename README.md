# RAGz

A small Python app for exploring public neuroscience clinical trial protocols with local semantic search and optional cited Gemini explanations.

Choose Alzheimer's disease, Parkinson's disease, or mild cognitive impairment; filter registry records; compare up to three trials; and retrieve passages about study design, interventions, outcomes, or participant criteria. No patient uploads or personal health questions are accepted.

## Run locally

```bash
git clone https://github.com/aralcimcim/ragz.git
cd ragz
conda env create -f environment.yml
conda activate ragz
python -m pip install -r requirements.txt
python build_index.py
python -m streamlit run app.py --server.port 8503
```

Open the local URL printed by Streamlit. The default index contains up to 30 recently updated Alzheimer's trial records. To include all three topics:

```bash
python build_index.py --topic All --limit 30
```

Each build replaces the previous index. The first build downloads a small embedding model, runs it on CPU, and saves public source records, model files, and an SQLite vector index under `.local/`. No GPU, Azure subscription, or language model API key is needed for search and comparisons.

## Optional Gemini explanation

```bash
cp .env.example .env
```

Set your own `GEMINI_API_KEY` and an available `GEMINI_MODEL` in `.env`. Select **Find evidence**, then opt in to sending those public passages to Gemini and select **Explain evidence**. API usage may cost money according to your account. Keep `.env` out of Git; it is ignored.

Each generated claim must cite a retrieved source ID and an exact supporting quotation. Unknown sources and mismatched quotations reject the response. Matching quotations do not guarantee that the model's interpretation is correct.

## How it works

1. Download public records from the [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api).
2. Split protocol fields into overlapping passages and embed them with `BAAI/bge-small-en-v1.5` through FastEmbed.
3. Store records and vectors in SQLite. Filter records, then rank passages by cosine similarity, with at most two passages per trial.
4. Optionally send retrieved passages to Gemini for a structured, cited explanation.

The source snapshot records retrieval time and API version information. Registry links and last-update dates accompany the evidence. Rebuild to refresh it.

## Scope and limits

This is a research education prototype, not medical advice or a tool for diagnosis, treatment selection, or personal eligibility decisions. Registry entries describe study protocols; planned outcomes are not study findings. Results tables are not indexed, even when the registry's results-posted flag is true.

The corpus is a bounded condition search (up to 100 records per topic), sorted by latest registry update. It is not a systematic review. Search results are selected passages, not exhaustive comparisons. Registry records may be incomplete or outdated.

Only public records and preset questions enter the app's workflow. Hosting providers and API providers still have their own logging and data policies. Before an unrestricted public deployment, add request limits and configure spending limits and hosting; this repository does not deploy anything automatically.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic registry records and do not call Gemini.
