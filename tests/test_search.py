from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.sample_data import prepared_sample_documents
from app.search import (
    PROJECT_FIELDS,
    atlas_rank_fusion_search,
    client_rank_fusion_search,
    compare_search_modes,
    explain_search_pipeline,
    lexical_search_page,
    lexical_stage,
    vector_stage,
)
from app.synonyms import is_known_synonym_phrase, synonym_documents


class SearchPipelineTests(unittest.TestCase):
    def test_lexical_stage_keeps_geo_and_provider_scope_in_search_filter(self) -> None:
        stage = lexical_stage(
            "same day sore throat clinic",
            {"origin": "downtown", "max_distance": 10, "telehealth": True},
        )
        filters = stage["$search"]["compound"]["filter"]

        self.assertIn({"equals": {"path": "document_type", "value": "care_provider"}}, filters)
        self.assertTrue(any("geoWithin" in clause for clause in filters))
        self.assertIn({"equals": {"path": "telehealth", "value": True}}, filters)

        synonym_clauses = [
            clause["text"]
            for clause in stage["$search"]["compound"]["should"]
            if "text" in clause and clause["text"].get("synonyms")
        ]
        self.assertEqual(len(synonym_clauses), 1)
        self.assertEqual(synonym_clauses[0]["synonyms"], "medical_synonyms")
        self.assertNotIn("aliases", synonym_clauses[0]["path"])

        recall_gates = [clause["compound"] for clause in filters if "compound" in clause]
        self.assertEqual(len(recall_gates), 1)
        self.assertEqual(recall_gates[0]["minimumShouldMatch"], 3)
        self.assertEqual(
            [clause["text"]["query"] for clause in recall_gates[0]["should"]],
            ["same", "day", "sore", "throat", "clinic"],
        )

    def test_single_term_synonym_query_does_not_require_two_terms(self) -> None:
        stage = lexical_stage("otolaryngologist")
        filters = stage["$search"]["compound"]["filter"]

        self.assertFalse(any("compound" in clause for clause in filters))

    def test_operational_terms_do_not_admit_unrelated_clinical_results(self) -> None:
        stage = lexical_stage("rash doctor accepting new patients")
        recall_gate = next(clause["compound"] for clause in stage["$search"]["compound"]["filter"] if "compound" in clause)

        self.assertEqual(recall_gate["minimumShouldMatch"], 1)
        self.assertEqual([clause["text"]["query"] for clause in recall_gate["should"]], ["rash"])

    def test_exact_multiword_synonym_phrase_bypasses_literal_recall_gate(self) -> None:
        self.assertTrue(is_known_synonym_phrase("OB/GYN"))
        stage = lexical_stage("OB GYN")
        self.assertFalse(any("compound" in clause for clause in stage["$search"]["compound"]["filter"]))

    @patch("app.search.embed_query", return_value=[0.1] * 1024)
    def test_vector_stage_uses_twenty_x_candidate_window_and_provider_scope(self, _embed: Mock) -> None:
        stage = vector_stage("sports injury doctor", limit=12)
        vector = stage["$vectorSearch"]

        self.assertEqual(vector["numCandidates"], 240)
        self.assertEqual(vector["filter"], {"document_type": {"$eq": "care_provider"}})

    @patch("app.search.embed_query", return_value=[0.1] * 1024)
    @patch("app.search.get_collection")
    def test_atlas_hybrid_executes_native_rank_fusion(self, collection_factory: Mock, _embed: Mock) -> None:
        collection = collection_factory.return_value
        collection.aggregate.return_value = iter(
            [
                {
                    "_id": "provider-1",
                    "provider_id": "fc-1",
                    "provider_name": "Example Orthopedics",
                    "location": {"type": "Point", "coordinates": [-97.74, 30.27]},
                    "score_details": {
                        "value": (0.55 / 61) + (0.45 / 62),
                        "details": [
                            {
                                "inputPipelineName": "lexicalPipeline",
                                "rank": 1,
                                "value": 18.2,
                                "weight": 0.55,
                            },
                            {
                                "inputPipelineName": "vectorPipeline",
                                "rank": 2,
                                "value": 0.81,
                                "weight": 0.45,
                            },
                            {
                                "inputPipelineName": "missingPipeline",
                                "rank": "NA",
                                "value": None,
                                "weight": None,
                            },
                        ],
                    },
                }
            ]
        )

        results = atlas_rank_fusion_search("knee surgeon", 8)
        pipeline = collection.aggregate.call_args.args[0]

        self.assertIn("$rankFusion", pipeline[0])
        self.assertEqual(pipeline[0]["$rankFusion"]["combination"]["weights"]["lexicalPipeline"], 0.55)
        self.assertEqual(results[0]["score_type"], "scoreDetails")
        self.assertEqual(results[0]["fusion"]["lexical"]["rank"], 1)
        self.assertNotIn("missing", results[0]["fusion"])
        self.assertAlmostEqual(results[0]["fusion"]["lexical"]["contribution"], 0.55 / 61)
        self.assertAlmostEqual(results[0]["fusion"]["vector"]["contribution"], 0.45 / 62)
        self.assertAlmostEqual(
            results[0]["score"],
            results[0]["fusion"]["lexical"]["contribution"]
            + results[0]["fusion"]["vector"]["contribution"],
        )

    @patch("app.search.vector_search", return_value=[])
    @patch("app.search.lexical_search", return_value=[])
    @patch("app.search.atlas_rank_fusion_search", return_value=[])
    @patch("app.search.embed_query", return_value=[0.1] * 1024)
    @patch("app.search.get_settings")
    def test_compare_modes_reuses_one_query_embedding(
        self,
        get_settings: Mock,
        embed: Mock,
        hybrid: Mock,
        lexical: Mock,
        vector: Mock,
    ) -> None:
        get_settings.return_value.use_atlas_rank_fusion = True

        result = compare_search_modes("sports injury", limit=12)

        embed.assert_called_once_with("sports injury")
        vector.assert_called_once_with("sports injury", 12, None, query_vector=embed.return_value)
        hybrid.assert_called_once_with("sports injury", 12, None, query_vector=embed.return_value)
        lexical.assert_called_once_with("sports injury", 12, None)
        self.assertEqual([item["execution"] for item in result["comparison"]], ["$search", "$vectorSearch", "$rankFusion"])

    @patch("app.search.vector_search")
    @patch("app.search.lexical_search")
    def test_client_fusion_preserves_selected_weights(
        self,
        lexical: Mock,
        vector: Mock,
    ) -> None:
        lexical.return_value = [{"_id": "one", "score": 4.2}]
        vector.return_value = [{"_id": "one", "score": 0.9}]

        result = client_rank_fusion_search(
            "sports injury",
            1,
            profile="precision",
            query_vector=[0.1] * 1024,
        )

        self.assertEqual(result[0]["fusion"]["lexical"]["weight"], 0.75)
        self.assertEqual(result[0]["fusion"]["vector"]["weight"], 0.25)

    def test_explained_pipeline_matches_live_candidate_windows(self) -> None:
        vector = explain_search_pipeline("knee surgeon", "vector", limit=12, rerank=True)
        self.assertEqual(vector[0]["$vectorSearch"]["limit"], 20)
        self.assertEqual(vector[0]["$vectorSearch"]["numCandidates"], 400)

        hybrid = explain_search_pipeline("knee surgeon", "hybrid", limit=12)
        rank_fusion = hybrid[0]["$rankFusion"]
        self.assertEqual(rank_fusion["input"]["pipelines"]["lexicalPipeline"][-1], {"$limit": 60})
        self.assertEqual(rank_fusion["input"]["pipelines"]["vectorPipeline"][0]["$vectorSearch"]["limit"], 60)
        self.assertEqual(hybrid[1], {"$limit": 12})

    @patch("app.search.get_collection")
    def test_lexical_pagination_uses_stable_search_after_token(self, collection_factory: Mock) -> None:
        collection = collection_factory.return_value
        collection.aggregate.return_value = iter(
            [
                {
                    "provider_id": "fc-1",
                    "provider_name": "Example Care",
                    "pagination_token": "next-page-token",
                }
            ]
        )

        results, next_token = lexical_search_page(
            "primary care",
            1,
            search_after="current-page-token",
        )
        pipeline = collection.aggregate.call_args.args[0]

        self.assertEqual(pipeline[0]["$search"]["searchAfter"], "current-page-token")
        self.assertEqual(
            pipeline[0]["$search"]["sort"],
            {"score": {"$meta": "searchScore"}, "provider_id": 1},
        )
        self.assertEqual(next_token, "next-page-token")
        self.assertEqual(results[0]["provider_name"], "Example Care")

    def test_search_indexes_cover_every_query_path_without_projected_only_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        search_definition = json.loads((root / "indexes/search_index.json").read_text())
        vector_definition = json.loads((root / "indexes/vector_index.json").read_text())

        search_fields = set(search_definition["mappings"]["fields"])
        required_search_fields = {
            "document_type",
            "provider_id",
            "provider_name",
            "provider_type",
            "specialty_name",
            "specialty_group",
            "aliases",
            "conditions",
            "procedures",
            "splunk_user_keywords",
            "care_summary",
            "autocomplete_text",
            "insurance_networks",
            "languages",
            "specialty_filter",
            "networks_filter",
            "languages_filter",
            "city",
            "location",
            "rating",
            "accepting_new_patients",
            "telehealth",
        }
        self.assertEqual(search_fields, required_search_fields)
        self.assertFalse(search_definition["mappings"]["dynamic"])

        vector_paths = {field["path"] for field in vector_definition["fields"]}
        self.assertEqual(
            vector_paths,
            {
                "embedding",
                "document_type",
                "specialty_filter",
                "networks_filter",
                "languages_filter",
                "accepting_new_patients",
                "telehealth",
                "rating",
            },
        )

    def test_member_decision_fields_are_stored_but_not_search_indexed(self) -> None:
        documents = prepared_sample_documents()
        search_fields = json.loads(
            (Path(__file__).resolve().parents[1] / "indexes/search_index.json").read_text()
        )["mappings"]["fields"]

        for field in ("address_line1", "phone", "next_available"):
            self.assertTrue(all(document.get(field) for document in documents))
            self.assertIn(field, PROJECT_FIELDS)
            self.assertNotIn(field, search_fields)
        self.assertEqual(len({document["phone"] for document in documents}), len(documents))

    def test_medical_synonym_source_uses_supported_atlas_shapes(self) -> None:
        documents = synonym_documents()
        self.assertGreaterEqual(len(documents), 10)
        self.assertTrue(all(document["mappingType"] in {"equivalent", "explicit"} for document in documents))
        self.assertTrue(all(len(document.get("synonyms", [])) >= 1 for document in documents))


if __name__ == "__main__":
    unittest.main()
