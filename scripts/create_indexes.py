import json
from copy import deepcopy
from pathlib import Path

from pymongo.operations import SearchIndexModel

from app.config import get_settings
from app.db import get_collection


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def index_definitions() -> dict:
    settings = get_settings()
    definitions = {
        "vector": load_json(ROOT / "indexes" / "vector_index.json"),
        "fullText": load_json(ROOT / "indexes" / "search_index.json"),
        "geospatial": {"location": "2dsphere"},
    }
    synonym_mapping = definitions["fullText"]["synonyms"][0]
    synonym_mapping["name"] = settings.synonym_mapping_name
    synonym_mapping["source"]["collection"] = settings.synonym_collection
    return deepcopy(definitions)


def main() -> None:
    settings = get_settings()
    collection = get_collection()
    definitions = index_definitions()

    synonym_count = collection.database[settings.synonym_collection].count_documents({})
    if synonym_count == 0:
        raise SystemExit(
            f"Synonym source {settings.atlas_db}.{settings.synonym_collection} is empty. "
            "Run `make synonyms` before creating the Search index."
        )

    indexes = [
        SearchIndexModel(
            definition=definitions["vector"],
            name=settings.vector_index_name,
            type="vectorSearch",
        ),
        SearchIndexModel(
            definition=definitions["fullText"],
            name=settings.search_index_name,
        ),
    ]

    existing = {index["name"] for index in collection.list_search_indexes()}
    created_or_updated = []
    for index in indexes:
        name = index.document["name"]
        definition = index.document["definition"]
        if name in existing:
            collection.update_search_index(name, definition)
            created_or_updated.append(f"{name} (updated)")
        else:
            collection.create_search_index(index)
            created_or_updated.append(f"{name} (created)")

    collection.create_index([("location", "2dsphere")], name="location_2dsphere")
    print("Requested search indexes:")
    for name in created_or_updated:
        print(f"- {name}")
    print("- location_2dsphere")
    print(f"- {settings.synonym_mapping_name} ({synonym_count} synonym mappings)")
    print("Atlas may need a few minutes before the indexes are queryable.")


if __name__ == "__main__":
    main()
