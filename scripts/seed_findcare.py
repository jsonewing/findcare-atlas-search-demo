from __future__ import annotations

from app.config import get_settings
from app.db import get_collection
from app.embeddings import embed_texts
from app.sample_data import prepared_sample_documents
from scripts.seed_synonyms import seed_synonyms


def main() -> None:
    settings = get_settings()
    collection = get_collection()
    documents = prepared_sample_documents()
    embeddings = embed_texts((document["embedding_text"] for document in documents), input_type="document")

    for document, embedding in zip(documents, embeddings, strict=True):
        document["embedding"] = embedding
        document["embedding_model"] = settings.voyage_embed_model
        document["embedding_dimensions"] = settings.voyage_embed_dimensions

    # Keep the demo deterministic while preserving unrelated documents that may
    # intentionally share the same development collection.
    collection.delete_many(
        {"$or": [{"document_type": "care_provider"}, {"provider_id": {"$exists": True}}]}
    )
    if documents:
        collection.insert_many(documents)

    synonym_count = seed_synonyms()

    print(f"Seeded {len(documents)} FindCare provider documents into {settings.atlas_db}.{settings.atlas_collection}.")
    print(f"Seeded {synonym_count} medical synonym mappings into {settings.atlas_db}.{settings.synonym_collection}.")
    print(f"Embedding model: {settings.voyage_embed_model} ({settings.voyage_embed_dimensions} dimensions)")


if __name__ == "__main__":
    main()
