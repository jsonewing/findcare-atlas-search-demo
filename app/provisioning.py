from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
import json
from pathlib import Path
import time
from typing import Any

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel
import voyageai

from app.config import ROOT, Settings
from app.sample_data import prepared_sample_documents
from app.synonyms import synonym_documents
from scripts.create_indexes import index_definitions


PROVIDER_FIXTURE = ROOT / "data" / "findcare_providers.json"


def bundled_provider_documents(path: Path = PROVIDER_FIXTURE) -> list[dict[str, Any]]:
    if path.is_file():
        documents = json.loads(path.read_text(encoding="utf-8"))
    else:
        documents = prepared_sample_documents()
    if not isinstance(documents, list) or not documents:
        raise ValueError("The bundled FindCare provider fixture is empty or invalid.")
    if any(not document.get("provider_id") for document in documents):
        raise ValueError("Every bundled provider must include provider_id.")
    return deepcopy(documents)


def _search_index_status(collection) -> dict[str, dict[str, Any]]:
    try:
        return {
            item["name"]: {
                "status": item.get("status", "UNKNOWN"),
                "queryable": bool(item.get("queryable", False)),
            }
            for item in collection.list_search_indexes()
        }
    except OperationFailure as exc:
        if exc.code == 26:  # NamespaceNotFound for a new target collection.
            return {}
        raise


def provision_demo_events(
    atlas_uri: str,
    voyage_api_key: str,
    database: str,
    collection_name: str,
    settings: Settings,
    wait_seconds: int = 240,
) -> Iterator[dict[str, Any]]:
    client = MongoClient(
        atlas_uri,
        appname="findcare-portable-provisioning",
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
    )
    try:
        collection = client[database][collection_name]
        bundled = bundled_provider_documents()
        bundled_ids = [document["provider_id"] for document in bundled]
        existing_ids = {
            item["provider_id"]
            for item in collection.find(
                {"provider_id": {"$in": bundled_ids}},
                {"_id": 0, "provider_id": 1},
            )
        }
        missing = [document for document in bundled if document["provider_id"] not in existing_ids]

        if missing:
            yield {
                "message": f"Generating Voyage 4 embeddings for {len(missing)} bundled providers",
                "detail": "embeddings",
            }
            response = voyageai.Client(api_key=voyage_api_key).embed(
                [document["embedding_text"] for document in missing],
                model=settings.voyage_embed_model,
                input_type="document",
                output_dimension=settings.voyage_embed_dimensions,
            )
            operations = []
            for document, embedding in zip(missing, response.embeddings, strict=True):
                document["embedding"] = embedding
                document["embedding_model"] = settings.voyage_embed_model
                document["embedding_dimensions"] = settings.voyage_embed_dimensions
                operations.append(
                    ReplaceOne(
                        {"provider_id": document["provider_id"]},
                        document,
                        upsert=True,
                    )
                )
            collection.bulk_write(operations, ordered=False)
            yield {
                "message": f"Loaded {len(missing)} bundled providers into Atlas",
                "detail": "providers",
            }
        else:
            yield {
                "message": f"All {len(bundled)} bundled providers already exist",
                "detail": "providers",
            }

        synonyms = synonym_documents()
        synonym_collection = collection.database[settings.synonym_collection]
        for index, document in enumerate(synonyms, start=1):
            synonym_collection.replace_one(
                {"_id": f"findcare-medical-synonym-{index:02d}"},
                {"_id": f"findcare-medical-synonym-{index:02d}", **document},
                upsert=True,
            )
        yield {
            "message": f"Prepared {len(synonyms)} packaged medical synonym mappings",
            "detail": "synonyms",
        }

        definitions = index_definitions()
        existing_indexes = _search_index_status(collection)
        search_models = (
            SearchIndexModel(
                definition=definitions["vector"],
                name=settings.vector_index_name,
                type="vectorSearch",
            ),
            SearchIndexModel(
                definition=definitions["fullText"],
                name=settings.search_index_name,
            ),
        )
        requested = []
        for model in search_models:
            name = model.document["name"]
            if name not in existing_indexes:
                collection.create_search_index(model)
                requested.append(name)
        collection.create_index([("location", "2dsphere")], name="location_2dsphere")
        yield {
            "message": (
                f"Requested {', '.join(requested)}; waiting for Atlas"
                if requested
                else "Search, vector, and geospatial indexes already exist"
            ),
            "detail": "indexes",
        }

        required = (settings.search_index_name, settings.vector_index_name)
        deadline = time.monotonic() + wait_seconds
        while True:
            statuses = _search_index_status(collection)
            ready_count = sum(bool(statuses.get(name, {}).get("queryable")) for name in required)
            if ready_count == len(required):
                yield {
                    "message": f"{len(bundled)} providers and all search indexes are ready",
                    "detail": "ready",
                }
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Atlas accepted the demo assets, but the search indexes are still building. "
                    "Wait a few minutes and run setup again."
                )
            yield {
                "message": f"Atlas is building search indexes ({ready_count}/{len(required)} queryable)",
                "detail": "waiting",
            }
            time.sleep(3)
    finally:
        client.close()
