"""Regression tests for scripts/dashboard.py.

Run from the repo root: python3 -m unittest discover -s tests
"""

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dashboard", ROOT / "scripts" / "dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


def build(sessions=(), history=(), profile=None):
    return dashboard.build({"profile": profile or {}, "sessions": list(sessions),
                            "history": list(history)}, "test")


class DashboardTest(unittest.TestCase):
    def test_watch_status_renders_in_watching_tab(self):
        """The string 'watch' is the documented contract between SKILL.md,
        references/storage.md and dashboard.py. Roles sourced but not yet applied
        to are stored as sessions with this status; anything else strands them
        where the dashboard cannot show them."""
        html = build(sessions=[{"company": "Acme", "role": "Senior AI PM",
                                "status": "watch", "url": "https://example.com/j/1",
                                "pendingFields": []}])
        self.assertIn("Watching", html)
        self.assertIn("Acme", html)
        self.assertIn("https://example.com/j/1", html)

    def test_watch_entries_are_not_counted_as_applications(self):
        """A watch entry is a sourced role, not a submission. Counting one as an
        application would overstate the funnel and hide that nothing went out."""
        html = build(sessions=[{"company": "Acme", "role": "Senior AI PM",
                                "status": "watch", "pendingFields": []}])
        self.assertIn('Needs you<span class="n">0</span>', html)
        self.assertIn('Watching<span class="n">1</span>', html)

    def test_safe_url_blocks_non_http_schemes(self):
        self.assertEqual(dashboard.safe_url("javascript:alert(1)"), "")
        self.assertEqual(dashboard.safe_url("data:text/html,x"), "")
        self.assertEqual(dashboard.safe_url(None), "")
        self.assertEqual(dashboard.safe_url("https://ok.example"), "https://ok.example")

    def test_scraped_javascript_url_never_reaches_href(self):
        html = build(sessions=[{"company": "X", "role": "PM", "status": "active",
                                "url": "javascript:alert(1)", "pendingFields": []}])
        self.assertNotIn("javascript:", html)

    def test_markup_in_store_data_is_escaped(self):
        html = build(sessions=[{"company": "<script>x</script>", "role": "PM",
                                "status": "active", "pendingFields": []}])
        self.assertNotIn("<script>x", html)

    def test_outcome_keeps_application_on_submitted_tab(self):
        html = build(history=[{"event": "interview", "company": "A", "role": "PM", "at": "2026-08-15"}])
        self.assertIn("interview", html)
        self.assertNotIn("Nothing submitted yet", html)

    def test_orphaned_submitting_is_flagged(self):
        html = build(history=[{"event": "submitting", "company": "C", "role": "PM", "at": "2026-08-15"}])
        self.assertIn("submission attempted, interrupted", html)

    def test_completed_not_flagged_as_unconfirmed(self):
        html = build(history=[{"event": "completed", "company": "C", "role": "PM", "at": "2026-08-15"}])
        self.assertNotIn("Not confirmed submitted", html)


if __name__ == "__main__":
    unittest.main()
