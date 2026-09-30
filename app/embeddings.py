from collections.abc import Iterable
from functools import lru_cache

import voyageai

from app.config import get_settings


@lru_cache
def get_voyage_client() -> voyageai.Client:
    settings = get_settings()
    settings.validate()
    return voyageai.Client(api_key=settings.voyage_api_key)


def embed_texts(texts: Iterable[str], input_type: str) -> list[list[float]]:
    settings = get_settings()
    batch = list(texts)
    if not batch:
        return []

    result = get_voyage_client().embed(
        batch,
        model=settings.voyage_embed_model,
        input_type=input_type,
        output_dimension=settings.voyage_embed_dimensions,
    )
    return result.embeddings


def embed_query(query: str) -> list[float]:
    return embed_texts([query], input_type="query")[0]


def rerank_documents(query: str, documents: list[str], top_k: int | None = None):
    settings = get_settings()
    if not documents:
        return []
    return get_voyage_client().rerank(
        query=query,
        documents=documents,
        model=settings.voyage_rerank_model,
        top_k=top_k,
    ).results


def close_voyage_client() -> None:
    get_voyage_client.cache_clear()
