from __future__ import annotations

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class PortableApiTests(unittest.TestCase):
    @patch("app.main.setup_summary", return_value={"configured": False})
    def test_readiness_does_not_require_credentials(self, _summary) -> None:
        with TestClient(app) as client:
            response = client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready", "configured": False})

    @patch("app.main.setup_summary")
    def test_setup_status_never_returns_credentials(self, setup_summary) -> None:
        setup_summary.return_value = {
            "configured": True,
            "atlas_configured": True,
            "voyage_configured": True,
            "atlas_target": "example.mongodb.net",
            "database": "findcare_demo",
            "collection": "care_providers",
            "storage": ".env in this FindCare folder",
        }
        with TestClient(app) as client:
            response = client.get("/api/setup")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("atlas_uri", response.json())
        self.assertNotIn("voyage_api_key", response.json())
        self.assertNotIn("password", response.text)

    @patch("app.main.configure_local_events")
    def test_streamed_setup_never_returns_submitted_secrets(self, configure_events) -> None:
        configure_events.return_value = iter(
            [
                {"stage": "atlas", "status": "complete", "message": "Atlas connected"},
                {
                    "stage": "ready",
                    "status": "complete",
                    "message": "FindCare is ready",
                    "setup": {"configured": True, "atlas_target": "example.mongodb.net"},
                },
            ]
        )
        uri = "mongodb+srv://user:secret@example.mongodb.net/"
        key = "pa-secret-value"
        with TestClient(app) as client:
            response = client.post(
                "/api/setup",
                json={
                    "atlas_uri": uri,
                    "voyage_api_key": key,
                    "database": "findcare_demo",
                    "collection": "care_providers",
                },
            )
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1]["setup"]["atlas_target"], "example.mongodb.net")
        self.assertNotIn("secret", response.text)
        configure_events.assert_called_once_with(uri, key, "findcare_demo", "care_providers", True)

    @patch("app.main.get_settings")
    def test_health_reports_unconfigured_without_connecting(self, get_settings) -> None:
        get_settings.return_value = SimpleNamespace(
            atlas_uri="",
            voyage_api_key="",
            atlas_db="findcare_demo",
            atlas_collection="care_providers",
            use_atlas_rank_fusion=False,
        )
        with patch("app.main.get_collection") as get_collection:
            with TestClient(app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        get_collection.assert_not_called()

    @patch("app.main.get_collection")
    @patch("app.main.get_settings")
    def test_health_reports_atlas_outage_without_leaking_details(
        self,
        get_settings,
        get_collection,
    ) -> None:
        get_settings.return_value = SimpleNamespace(
            atlas_uri="mongodb+srv://user:private-password@example.mongodb.net/",
            voyage_api_key="pa-private-key",
            atlas_db="findcare_demo",
            atlas_collection="care_providers",
            use_atlas_rank_fusion=True,
        )
        get_collection.return_value.count_documents.side_effect = RuntimeError(
            "private-password pa-private-key"
        )

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": False,
                "configured": True,
                "database": "findcare_demo",
                "collection": "care_providers",
                "documents": 0,
                "collectionDocuments": 0,
                "rankFusionEnabled": True,
                "indexes": {},
                "error": "Atlas is unavailable",
            },
        )
        self.assertNotIn("private-password", response.text)
        self.assertNotIn("pa-private-key", response.text)

    @patch("app.main.search_providers_with_metrics")
    def test_search_failure_returns_generic_service_error(self, search) -> None:
        search.side_effect = RuntimeError(
            "mongodb+srv://user:private-password@example.mongodb.net pa-private-key"
        )

        with TestClient(app) as client:
            response = client.post(
                "/search",
                json={"query": "knee replacement", "mode": "hybrid"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Search services are unavailable. Check Atlas connectivity and try again."},
        )
        self.assertNotIn("private-password", response.text)
        self.assertNotIn("pa-private-key", response.text)


if __name__ == "__main__":
    unittest.main()
