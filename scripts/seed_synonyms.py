from __future__ import annotations

from app.config import get_settings
from app.db import get_collection
from app.synonyms import synonym_documents


def seed_synonyms() -> int:
    settings = get_settings()
    collection = get_collection().database[settings.synonym_collection]
    documents = synonym_documents()
    collection.delete_many({})
    if documents:
        collection.insert_many(documents)
    return len(documents)


def main() -> None:
    settings = get_settings()
    count = seed_synonyms()
    print(f"Seeded {count} medical synonym mappings into {settings.atlas_db}.{settings.synonym_collection}.")


if __name__ == "__main__":
    main()
