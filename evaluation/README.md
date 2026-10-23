# Small labelled retrieval evaluation

This is a development benchmark, separate from software behaviour tests. Questions and labels were authored by the coding assistant from the source passages before running retrieval; they have **not** been independently reviewed by a neuroscience researcher. No model training, parameter tuning, or generation API is involved.

## Run

From the repository root, with the app dependencies installed:

```bash
python evaluation/run.py
```

The first run may download the CPU embedding model. Subsequent runs can use `HF_HUB_OFFLINE=1 python evaluation/run.py` when the model is cached. The evaluation embeds the committed `corpus.json`; it does not fetch current records or replace the app's index. Results overwrite `results.json`.

## Questions and labels

`questions.json` contains 12 source-derived factual questions, labelled source IDs, and exact supporting quotations. They cover intervention details and planned outcomes, including stimulation parameters, assessment windows, therapy schedules, and study measurements. The runner checks every quotation against the corpus before scoring.

`corpus.json` freezes 119 public ClinicalTrials.gov records and all 911 indexed passages, including distractors. Original registry metadata, source URLs, and last-update dates are preserved. These are protocol descriptions, not evidence that the interventions work. See the main README for data sources and scope.

Each question searches **all 119 trials without topic/status filters**, using the production `retrieval.retrieve()` function and its two-passages-per-trial cap. The local BGE model embeds the questions and frozen passages. These free-text questions evaluate the underlying retriever, not the app's preset-question canvas or multi-question interleaving.

## Metric

**Hit@5** is the fraction of questions for which at least one labelled supporting passage appears in the first five results. It is not precision@5 or recall over every relevant passage. `results.json` records each question's retrieved IDs, first-support rank, misses, corpus/question hashes, embedding model, settings, and FastEmbed version.

## Measured result

**9 / 12 questions had their labelled supporting passage in the top five (Hit@5 = 75%).**

Three questions missed: MusicGlove stimulation-session counts (R06), the eptinezumab primary endpoint/window (R09), and the childhood brain-imaging primary measurement (R11). In each case an overview passage from the correct trial appeared, but the specifically labelled intervention/outcome passage did not. Finding the right trial is not counted as finding the supporting passage. No labels or ranking parameters were changed after seeing these results.

## Limits and next evaluation

This is a small, source-derived development set, not a held-out user benchmark. One question changes the score by about 8.3 percentage points. Labels identify specific supporting passages rather than exhaustively judging every possible answer passage. There are no unanswerable questions, expert adjudication, generation-quality measurements, or clinical validation. Embedding weights are identified by model name rather than a pinned artifact hash, so runtime/model changes may change results.

Before tuning, have an independent reviewer check the labels and add a separate held-out set of realistic questions, paraphrases, and absent-evidence cases. Keep these initial labels and failures visible when comparing future retrieval versions.
