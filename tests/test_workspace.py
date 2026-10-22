import unittest

import numpy as np

from workspace import catalog_for, default_map, map_evidence, question_keys, search_map, trial_scope, validate_map


TRIALS = [
    {"nct_id": "NCT00000001", "topic": "Topic A", "topics": ["Topic A", "Topic B"], "status": "RECRUITING", "study_type": "INTERVENTIONAL"},
    {"nct_id": "NCT00000002", "topic": "Topic A", "status": "COMPLETED", "study_type": "OBSERVATIONAL"},
    {"nct_id": "NCT00000003", "topic": "Topic B", "status": "COMPLETED", "study_type": "INTERVENTIONAL"},
]


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog_for(TRIALS, ["Topic A", "Topic B"])

    def state_for(self, *values):
        ids = [c["id"] for c in self.catalog if c["value"] in values]
        return validate_map({"ids": ids}, self.catalog)

    def test_starter_is_a_valid_connected_question(self):
        state = validate_map(default_map(self.catalog), self.catalog)
        self.assertEqual(question_keys(state, self.catalog), ["Study design"])
        self.assertEqual(len(trial_scope(TRIALS, state, self.catalog)), 2)

    def test_topic_union_and_filter_intersection(self):
        state = self.state_for("Topic A", "Topic B", "COMPLETED", "INTERVENTIONAL")
        self.assertEqual([t["nct_id"] for t in trial_scope(TRIALS, state, self.catalog)], ["NCT00000003"])
        state = self.state_for("Topic A", "Topic B", "RECRUITING", "COMPLETED")
        self.assertEqual(len(trial_scope(TRIALS, state, self.catalog)), 3)

    def test_no_topic_does_not_search_all_trials(self):
        self.assertEqual(trial_scope(TRIALS, self.state_for("Study design"), self.catalog), [])

    def test_results_flag_is_a_scope_filter(self):
        records = [{**t, "has_results": t["nct_id"] == "NCT00000002"} for t in TRIALS]
        state = self.state_for("Topic A", "results_posted")
        self.assertEqual([t["nct_id"] for t in trial_scope(records, state, self.catalog)], ["NCT00000002"])

    def test_map_capacity_is_enforced_server_side(self):
        with self.assertRaises(ValueError):
            validate_map({"ids": [c["id"] for c in self.catalog[:9]]}, self.catalog)

    def test_map_rejects_unknown_duplicate_and_nonfinite_values(self):
        for value in ({"ids": ["personal-input"]}, {"ids": ["topic:0", "topic:0"]},
                      {"ids": ["topic:0"], "positions": {"topic:0": {"x": float("nan"), "y": 10}}},
                      {"ids": ["topic:0"], "positions": {"topic:0": {"x": True, "y": 10}}}):
            with self.assertRaises(ValueError):
                validate_map(value, self.catalog)

    def test_positions_are_clamped_and_do_not_change_query_scope(self):
        state = self.state_for("Topic A", "Study design")
        before = trial_scope(TRIALS, state, self.catalog)
        state["positions"]["topic:0"] = {"x": -500, "y": 900}
        state = validate_map(state, self.catalog)
        self.assertEqual(state["positions"]["topic:0"], {"x": 10, "y": 440})
        self.assertEqual(trial_scope(TRIALS, state, self.catalog), before)

    def test_combined_questions_get_individual_searches(self):
        chunks = [{"source_id": f"{nct}:{kind}", "nct_id": nct, "section": kind,
                   "text": f"{kind} evidence", "title": "Synthetic", "url": "https://clinicaltrials.gov/"}
                  for nct in ("NCT00000001", "NCT00000002") for kind in ("design", "outcomes")]
        vectors = np.array([[1., 0.], [0., 1.], [1., 0.], [0., 1.]])
        class Embedder:
            def __init__(self):
                self.calls = []
            def query_embed(self, query):
                self.calls.append(query)
                yield np.array([0., 1.] if "primary outcomes" in query else [1., 0.])
        embedder = Embedder()
        hits = search_map(chunks, vectors, {"NCT00000001", "NCT00000002"},
                          ["Study design", "Primary outcomes"], embedder)
        self.assertEqual(len(embedder.calls), 2)
        self.assertEqual([h["section"] for h in hits[:2]], ["design", "outcomes"])
        self.assertEqual(len({h["source_id"] for h in hits}), len(hits))
        self.assertTrue(all(sum(h["nct_id"] == nct for h in hits) <= 2 for nct in ("NCT00000001", "NCT00000002")))
        records = map_evidence(hits)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(records[0]["passages"]), 2)

    def test_invalid_scope_does_not_embed(self):
        class Embedder:
            def query_embed(self, query):
                raise AssertionError("Should not embed")
        for ids, questions in ((set(), ["Study design"]), ({"NCT00000001"}, ["Personal health question"])):
            with self.assertRaises(ValueError):
                search_map([], np.zeros((0, 2)), ids, questions, Embedder())


if __name__ == "__main__":
    unittest.main()
