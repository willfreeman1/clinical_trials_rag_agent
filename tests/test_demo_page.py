"""The demo page is served from the Flask app. No GPU."""

from __future__ import annotations

import unittest
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "demo" / "seed"


@unittest.skipUnless((SEED / "embeddings.npz").exists(), "demo seed not built")
class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from service.app import app

        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_index_names_the_disclaimer(self) -> None:
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
            text = response.get_data(as_text=True)
            self.assertIn("does not say a patient qualifies", text)
            self.assertIn("/static/app.js", text)
        finally:
            response.close()

    def test_patients_include_the_full_note(self) -> None:
        response = self.client.get("/v1/patients")
        try:
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual(body["model_mode"], "replay")
            ids = {row["patient_id"] for row in body["patients"]}
            self.assertEqual(ids, {"1", "8", "18"})
            one = next(row for row in body["patients"] if row["patient_id"] == "1")
            self.assertIn("GnRH", one["note"])
            self.assertTrue(one["summary"])
        finally:
            response.close()

    def test_static_assets_are_served(self) -> None:
        js = self.client.get("/static/app.js")
        css = self.client.get("/static/app.css")
        try:
            self.assertEqual(js.status_code, 200)
            self.assertEqual(css.status_code, 200)
            script = js.get_data(as_text=True).lower()
            self.assertIn("express contradiction", script)
            self.assertNotIn("you qualify", script)
        finally:
            js.close()
            css.close()


if __name__ == "__main__":
    unittest.main()
