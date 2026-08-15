"""Regression tests for scripts/store.py.

Run from the repo root: python3 -m unittest discover -s tests
"""

import argparse
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("store", ROOT / "scripts" / "store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


def ns(**kw):
    return argparse.Namespace(**kw)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = str(pathlib.Path(self.tmp.name) / "store")
        store.cmd_init(ns(root=self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def put_answer(self, question, value, state="confirmed", remember=False):
        f = pathlib.Path(self.tmp.name) / "in.json"
        f.write_text(json.dumps({"question": question, "value": value, "state": state}))
        return store.cmd_answer_put(ns(root=self.root, input=str(f), remember_sensitive=remember))

    def find(self, question):
        return store.cmd_answer_find(ns(root=self.root, question=question))

    def append_event(self, **event):
        f = pathlib.Path(self.tmp.name) / "ev.json"
        f.write_text(json.dumps(event))
        return store.cmd_history_append(ns(root=self.root, input=str(f)))

    # --- answer matching ------------------------------------------------

    def test_exact_match_roundtrip(self):
        self.put_answer("Notice period in days", "60")
        got = self.find("What is your notice period in days?")
        self.assertEqual(got["value"], "60")
        self.assertEqual(got["state"], "confirmed")

    def test_product_vs_project_does_not_fuzzy_match(self):
        # One word apart and the wrong answer; 0.71 overlap must stay below the bar.
        self.put_answer("Years of experience in product management", "6")
        got = self.find("Years of experience in project management")
        self.assertEqual(got["match"], "none")
        self.assertTrue(got["candidates"])
        self.assertNotIn("value", got["candidates"][0])

    def test_close_paraphrase_does_fuzzy_match(self):
        self.put_answer("Notice period in days", "60")
        got = self.find("Notice period days")
        self.assertEqual(got.get("match"), "fuzzy")
        self.assertEqual(got["value"], "60")

    def test_sensitive_never_fuzzy_matches(self):
        self.put_answer("What is your current CTC in INR?", "50 LPA",
                        state="sensitive", remember=True)
        got = self.find("Current CTC INR")  # 0.75 overlap: would match if not sensitive
        self.assertEqual(got["match"], "none")
        self.assertNotIn("value", got.get("candidates", [{}])[0])

    def test_sensitive_value_not_stored_without_consent(self):
        res = self.put_answer("Expected CTC", "70 LPA", state="sensitive", remember=False)
        self.assertFalse(res["stored"])
        got = self.find("Expected CTC")
        self.assertIsNone(got["value"])

    def test_answers_resolve_batches_and_validates(self):
        self.put_answer("Notice period in days", "60")
        f = pathlib.Path(self.tmp.name) / "qs.json"
        f.write_text(json.dumps(["Notice period in days", "Favourite colour"]))
        got = store.cmd_answers_resolve(ns(root=self.root, input=str(f)))
        self.assertEqual(got["Notice period in days"]["value"], "60")
        self.assertEqual(got["Favourite colour"]["match"], "none")
        f.write_text(json.dumps({"not": "a list"}))
        with self.assertRaises(store.StoreError):
            store.cmd_answers_resolve(ns(root=self.root, input=str(f)))

    # --- history and stats ------------------------------------------------

    def test_history_rejects_unknown_events_and_banned_keys(self):
        with self.assertRaises(store.StoreError):
            self.append_event(event="ghosted", company="X")
        with self.assertRaises(store.StoreError):
            self.append_event(event="completed", company="X", answers={"a": 1})

    def test_outcome_events_accepted(self):
        for e in ("submitting", "response", "interview", "offer", "rejected"):
            self.append_event(event=e, company="X", role="PM", applicationId="x-pm")

    def test_stats_funnel_sources_and_orphaned_submitting(self):
        self.append_event(event="completed", company="A", role="PM",
                          applicationId="a", source="linkedin")
        self.append_event(event="interview", company="A", role="PM", applicationId="a")
        self.append_event(event="completed", company="B", role="PM",
                          applicationId="b", source="greenhouse")
        self.append_event(event="submitting", company="C", role="PM", applicationId="c")
        got = store.cmd_stats(ns(root=self.root))
        self.assertEqual(got["applications"], 3)
        self.assertEqual(got["funnel"]["completed"], 2)
        self.assertEqual(got["bySource"]["linkedin"]["interview"], 1)
        self.assertEqual(got["bySource"]["greenhouse"]["interview"], 0)
        self.assertEqual(got["needsVerification"], ["C — PM"])

    # --- sessions and meta ------------------------------------------------

    def test_session_rejects_values_in_pending_fields(self):
        f = pathlib.Path(self.tmp.name) / "s.json"
        f.write_text(json.dumps({"company": "X", "pendingFields":
                                 [{"question": "CTC", "value": "50"}]}))
        with self.assertRaises(store.StoreError):
            store.cmd_session_save(ns(root=self.root, id="x", input=str(f)))

    def test_safe_id_rejects_traversal(self):
        with self.assertRaises(store.StoreError):
            store.safe_id("../evil")

    def test_meta_roundtrip(self):
        store.cmd_meta_set(ns(root=self.root, key="artifactUrl", value="https://x"))
        got = store.cmd_meta_get(ns(root=self.root, key="artifactUrl"))
        self.assertEqual(got["artifactUrl"], "https://x")


if __name__ == "__main__":
    unittest.main()
