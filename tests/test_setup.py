from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dotenv import dotenv_values

from app.setup import _atlas_target, _persist_env, configure_local_events


class SetupTests(unittest.TestCase):
    def test_atlas_target_redacts_credentials(self) -> None:
        target = _atlas_target("mongodb+srv://user:password@example.mongodb.net/?retryWrites=true")
        self.assertEqual(target, "example.mongodb.net")
        self.assertNotIn("password", target)

    def test_persist_env_is_private_and_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("USE_ATLAS_RANK_FUSION=true\n", encoding="utf-8")
            _persist_env(
                {
                    "ATLAS_URI": "mongodb+srv://user:p@cluster.mongodb.net/",
                    "VOYAGE_API_KEY": "pa-test-key-value",
                },
                env_path,
            )
            values = dotenv_values(env_path)
            self.assertEqual(values["USE_ATLAS_RANK_FUSION"], "true")
            self.assertEqual(values["VOYAGE_API_KEY"], "pa-test-key-value")
            self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)

    @patch("app.setup.setup_summary")
    @patch("app.setup.reload_settings")
    @patch("app.setup.close_voyage_client")
    @patch("app.setup.close_client")
    @patch("app.setup._persist_env")
    @patch("app.setup._validate_voyage")
    @patch("app.setup._validate_atlas")
    @patch("app.setup.get_settings")
    def test_blank_secrets_keep_existing_credentials_and_stream_progress(
        self,
        get_settings,
        validate_atlas,
        validate_voyage,
        persist_env,
        close_client,
        close_voyage_client,
        reload_settings,
        setup_summary,
    ) -> None:
        get_settings.return_value = SimpleNamespace(
            atlas_uri="mongodb+srv://saved@cluster.mongodb.net/",
            voyage_api_key="pa-saved-key-value",
        )
        validate_atlas.return_value = {
            "target": "cluster.mongodb.net",
            "documents": 100,
            "indexes": {
                "search_index": {"status": "READY", "queryable": True},
                "vector_index": {"status": "READY", "queryable": True},
            },
            "ready": True,
        }
        setup_summary.return_value = {"configured": True}

        events = list(configure_local_events("", "", "findcare_demo", "care_providers"))

        self.assertEqual(events[0]["stage"], "atlas")
        self.assertEqual(events[-1]["stage"], "ready")
        self.assertTrue(events[-1]["setup"]["configured"])
        validate_voyage.assert_called_once_with("pa-saved-key-value")
        persisted = persist_env.call_args.args[0]
        self.assertEqual(persisted["ATLAS_URI"], "mongodb+srv://saved@cluster.mongodb.net/")
        self.assertEqual(persisted["VOYAGE_API_KEY"], "pa-saved-key-value")
        close_client.assert_called_once()
        close_voyage_client.assert_called_once()
        reload_settings.assert_called_once_with(persisted)

    def test_incomplete_namespace_installs_bundled_demo_assets(self) -> None:
        current = SimpleNamespace(
            atlas_uri="",
            voyage_api_key="",
            search_index_name="search_index",
            vector_index_name="vector_index",
        )
        incomplete = {
            "target": "cluster.mongodb.net",
            "documents": 0,
            "indexes": {
                "search_index": {"status": "MISSING", "queryable": False},
                "vector_index": {"status": "MISSING", "queryable": False},
            },
            "ready": False,
        }
        ready = {
            "target": "cluster.mongodb.net",
            "documents": 100,
            "indexes": {
                "search_index": {"status": "READY", "queryable": True},
                "vector_index": {"status": "READY", "queryable": True},
            },
            "ready": True,
        }
        progress = [
            {"message": "Loaded 100 bundled providers", "detail": "providers"},
            {"message": "100 providers and all search indexes are ready", "detail": "ready"},
        ]

        with (
            patch("app.setup.get_settings", return_value=current),
            patch("app.setup._validate_atlas", side_effect=[incomplete, ready]) as validate_atlas,
            patch("app.setup._validate_voyage"),
            patch("app.setup.provision_demo_events", return_value=iter(progress)) as provision,
            patch("app.setup._persist_env"),
            patch("app.setup.close_client"),
            patch("app.setup.close_voyage_client"),
            patch("app.setup.reload_settings"),
            patch("app.setup.setup_summary", return_value={"configured": True}),
        ):
            events = list(
                configure_local_events(
                    "mongodb+srv://user:p@cluster.mongodb.net/",
                    "pa-valid-key-value",
                    "findcare_demo",
                    "care_providers",
                )
            )

        provision.assert_called_once()
        self.assertEqual(validate_atlas.call_count, 2)
        data_events = [event for event in events if event["stage"] == "data"]
        self.assertTrue(any("Loaded 100" in event["message"] for event in data_events))
        self.assertEqual(data_events[-1]["status"], "complete")
        self.assertTrue(events[-1]["setup"]["configured"])


if __name__ == "__main__":
    unittest.main()
