from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        self.atlas_uri = os.getenv("ATLAS_URI", "")
        self.atlas_db = os.getenv("ATLAS_DB", "findcare_demo")
        self.atlas_collection = os.getenv("ATLAS_COLLECTION", "care_providers")
        self.voyage_api_key = os.getenv("VOYAGE_API_KEY", "")
        self.voyage_embed_model = os.getenv("VOYAGE_EMBED_MODEL", "voyage-4")
        self.voyage_embed_dimensions = int(os.getenv("VOYAGE_EMBED_DIMENSIONS", "1024"))
        self.voyage_rerank_model = os.getenv("VOYAGE_RERANK_MODEL", "rerank-2")
        self.vector_index_name = os.getenv("VECTOR_INDEX_NAME", "vector_index")
        self.search_index_name = os.getenv("SEARCH_INDEX_NAME", "search_index")
        self.synonym_collection = os.getenv("SYNONYM_COLLECTION", "medical_synonyms")
        self.synonym_mapping_name = os.getenv("SYNONYM_MAPPING_NAME", "medical_synonyms")
        self.use_atlas_rank_fusion = os.getenv("USE_ATLAS_RANK_FUSION", "true").lower() == "true"

    def validate(self) -> None:
        missing = []
        if not self.atlas_uri:
            missing.append("ATLAS_URI")
        if not self.voyage_api_key:
            missing.append("VOYAGE_API_KEY")
        if missing:
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings(overrides: dict[str, str] | None = None) -> Settings:
    if overrides:
        os.environ.update(overrides)
    else:
        load_dotenv(ROOT / ".env", override=True)
    get_settings.cache_clear()
    return get_settings()
