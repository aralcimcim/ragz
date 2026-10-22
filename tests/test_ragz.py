import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from rag import Answer, Citation, Claim, summarize, validate_evidence
from retrieval import filter_trials, load_index, retrieve, save_index
from trials import make_chunks, normalize, split_text


def trial(nct="NCT00000001"):
    return normalize({"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": "Synthetic research study"},
        "descriptionModule": {"briefSummary": "A synthetic study of memory."},
        "designModule": {"studyType": "INTERVENTIONAL", "enrollmentInfo": {"count": 20, "type": "ESTIMATED"}},
        "outcomesModule": {"primaryOutcomes": [{"measure": "Memory score", "timeFrame": "12 weeks"}]},
    }}, "Alzheimer's disease")


class EvidenceTests(unittest.TestCase):
    def test_missing_fields_and_protocol_chunks(self):
        record = trial()
        self.assertEqual(record["allocation"], "Not reported")
        chunks = make_chunks(record)
        self.assertEqual(len(chunks), 5)
        design = next(c for c in chunks if c["section"] == "design")
        self.assertIn("20 (ESTIMATED)", design["text"])
        self.assertIn("12 weeks", next(c for c in chunks if c["section"] == "outcomes")["text"])

    def test_invalid_source_id_rejected(self):
        with self.assertRaises(ValueError):
            trial("https://example.org")

    def test_chunks_are_bounded_and_preserve_tail(self):
        content = "some research evidence " * 250 + "FINAL_MARKER"
        parts = list(split_text(content))
        self.assertTrue(all(len(p) <= 1200 for p in parts))
        self.assertTrue(parts[-1].endswith("FINAL_MARKER"))

    def test_filters_preserve_topic_overlap(self):
        record = trial()
        record["topics"] = [record["topic"], "Mild cognitive impairment"]
        self.assertEqual(filter_trials([record], "Mild cognitive impairment"), [record])
        self.assertEqual(filter_trials([record], record["topic"], results_only=True), [])
        self.assertEqual(filter_trials([record], record["topic"], status="COMPLETED"), [])

    def test_vector_roundtrip_filter_and_diversity(self):
        records = [trial(), trial("NCT00000002")]
        chunks = [c for t in records for c in make_chunks(t)]
        vectors = np.tile(np.array([1., 0.], dtype=np.float32), (len(chunks), 1))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trials.sqlite3"
            save_index(records, chunks, vectors, {"test": True}, path)
            restored, passages, matrix, metadata = load_index(path)
            self.assertEqual(restored, records)
            self.assertEqual(metadata, {"test": True})
            hits = retrieve(passages, matrix, [1., 0.], {records[1]["nct_id"]})
            self.assertEqual(len(hits), 2)
            self.assertTrue(all(h["nct_id"] == records[1]["nct_id"] for h in hits))
            self.assertEqual(retrieve(passages, matrix, [1., 0.], set()), [])

    def test_nonfinite_vectors_rejected(self):
        with self.assertRaises(ValueError):
            save_index([], [{}], np.array([[np.nan]]), {})

    def test_citations_must_match_retrieved_passages(self):
        hits = [{"source_id": "one", "text": "Primary outcome: Memory score"}]
        answer = Answer(claims=[Claim(text="Memory is assessed.", citations=[
            Citation(source_id="one", quote="Memory score")])], limitations="Synthetic example")
        self.assertIs(validate_evidence(answer, hits), answer)
        answer.claims[0].citations[0].quote = "Improved survival"
        with self.assertRaises(ValueError):
            validate_evidence(answer, hits)
        answer.claims[0].citations[0] = Citation(source_id="invented", quote="Memory score")
        with self.assertRaises(ValueError):
            validate_evidence(answer, hits)

    def test_no_api_call_without_evidence_or_preset(self):
        with patch("rag.genai.Client") as client:
            with self.assertRaises(ValueError):
                summarize("Study design", [])
            with self.assertRaises(ValueError):
                summarize("What treatment should I take?", [{"text": "example"}])
            client.assert_not_called()

    def test_generation_uses_structured_output_and_validates(self):
        answer = Answer(claims=[Claim(text="Memory is assessed.", citations=[
            Citation(source_id="one", quote="Memory score")])], limitations="Small snapshot")
        with patch("rag.genai.Client") as client, patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            api = client.return_value.__enter__.return_value
            api.models.generate_content.return_value.text = answer.model_dump_json()
            result = summarize("Primary outcomes", [{"source_id": "one", "text": "Memory score"}])
            self.assertEqual(result, answer)
            self.assertIsNone(api.models.generate_content.call_args.kwargs["config"].tools)

    def test_combined_preset_questions_are_sent_together(self):
        import json
        with patch("rag.genai.Client") as client, patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            api = client.return_value.__enter__.return_value
            api.models.generate_content.return_value.text = Answer(claims=[], limitations="Small snapshot").model_dump_json()
            summarize(["Study design", "Primary outcomes"], [{"source_id": "one", "text": "Memory score"}])
            contents = json.loads(api.models.generate_content.call_args.kwargs["contents"])
            self.assertEqual(len(contents["questions"]), 2)


if __name__ == "__main__":
    unittest.main()
