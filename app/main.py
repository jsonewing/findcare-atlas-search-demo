from contextlib import asynccontextmanager
import json
import logging
from time import perf_counter
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr

from app.config import ROOT, get_settings
from app.db import close_client, get_collection
from app.embeddings import close_voyage_client
from app.sample_data import MAP_ORIGINS, prepared_sample_documents
from app.search import (
    SearchMode,
    autocomplete,
    available_filters,
    compare_search_modes,
    explain_search_pipeline,
    lexical_search_page,
    map_providers,
    search_facets,
    search_providers_with_metrics,
)
from app.setup import configure_local_events, setup_summary
from scripts.create_indexes import index_definitions


logger = logging.getLogger(__name__)


def search_service_error(exc: Exception) -> HTTPException:
    logger.warning("Search service request failed (%s)", type(exc).__name__)
    return HTTPException(
        status_code=503,
        detail="Search services are unavailable. Check Atlas connectivity and try again.",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_voyage_client()
    close_client()


app = FastAPI(title="FindCare Atlas Search Demo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class SearchFilters(BaseModel):
    origin: str = "downtown"
    sort: Literal["relevance", "distance"] = "relevance"
    specialty: str | None = None
    network: str | None = None
    language: str | None = None
    accepting_new_patients: bool = False
    telehealth: bool = False
    max_distance: float | None = Field(default=None, ge=0, le=100)
    min_rating: float | None = Field(default=None, ge=0, le=5)

    def active(self) -> dict[str, Any]:
        return {key: value for key, value in self.model_dump().items() if value not in (None, "", False)}


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    mode: SearchMode = "hybrid"
    limit: int = Field(default=12, ge=1, le=24)
    rerank: bool = False
    hybrid_profile: Literal["balanced", "precision", "discovery"] = "balanced"
    page: int = Field(default=1, ge=1, le=100)
    page_token: str | None = Field(default=None, max_length=4096)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SetupRequest(BaseModel):
    atlas_uri: SecretStr | None = None
    voyage_api_key: SecretStr | None = None
    database: str = Field(default="findcare_demo", min_length=1, max_length=64)
    collection: str = Field(default="care_providers", min_length=1, max_length=64)
    install_demo_data: bool = True


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "static" / "styles.css")


@app.get("/app.js")
def javascript():
    return FileResponse(ROOT / "static" / "app.js")


@app.get("/austin-care-map.svg")
def map_asset():
    return FileResponse(ROOT / "static" / "austin-care-map.svg")


@app.get("/mongodb-leaf.svg")
def mongodb_leaf_asset():
    return FileResponse(ROOT / "static" / "mongodb-leaf.svg", media_type="image/svg+xml")


@app.get("/ready")
def ready():
    return {"status": "ready", "configured": setup_summary()["configured"]}


@app.get("/api/setup")
def setup_status():
    return setup_summary()


@app.post("/api/setup")
def save_setup(request: SetupRequest):
    atlas_uri = request.atlas_uri.get_secret_value() if request.atlas_uri else ""
    voyage_api_key = request.voyage_api_key.get_secret_value() if request.voyage_api_key else ""

    def stream():
        for event in configure_local_events(
            atlas_uri,
            voyage_api_key,
            request.database,
            request.collection,
            request.install_demo_data,
        ):
            yield json.dumps(event, separators=(",", ":")) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health():
    settings = get_settings()
    response = {
        "ok": False,
        "configured": bool(settings.atlas_uri and settings.voyage_api_key),
        "database": settings.atlas_db,
        "collection": settings.atlas_collection,
        "documents": 0,
        "collectionDocuments": 0,
        "rankFusionEnabled": settings.use_atlas_rank_fusion,
        "indexes": {},
    }
    if not settings.atlas_uri or not settings.voyage_api_key:
        return response

    try:
        collection = get_collection()
        response["documents"] = collection.count_documents({"document_type": "care_provider"})
        response["collectionDocuments"] = collection.estimated_document_count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Atlas health check failed (%s)", type(exc).__name__)
        return {**response, "error": "Atlas is unavailable"}

    try:
        response["indexes"] = {
            index["name"]: {"status": index.get("status"), "queryable": index.get("queryable", False)}
            for index in collection.list_search_indexes()
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Search index status check failed (%s)", type(exc).__name__)
    return {**response, "ok": True}


@app.post("/search")
def search(request: SearchRequest):
    request_started = perf_counter()
    pagination: dict[str, Any] = {"enabled": False, "strategy": None, "page": 1, "has_more": False}
    try:
        filters = request.filters.active()
        if request.mode == "lexical" and not request.rerank:
            retrieval_started = perf_counter()
            results, next_token = lexical_search_page(
                request.query,
                request.limit,
                filters=filters,
                search_after=request.page_token,
            )
            for rank, result in enumerate(results, start=1):
                result["original_rank"] = ((request.page - 1) * request.limit) + rank
                result["reranked"] = False
            execution = "$search"
            stage_timings = {
                "embedding_ms": 0.0,
                "retrieval_ms": round((perf_counter() - retrieval_started) * 1000, 1),
                "rerank_ms": 0.0,
            }
            pagination = {
                "enabled": True,
                "strategy": "searchSequenceToken",
                "page": request.page,
                "next_token": next_token,
                "has_more": bool(next_token),
            }
        else:
            results, execution, stage_timings = search_providers_with_metrics(
                request.query,
                request.mode,
                request.limit,
                filters=filters,
                rerank=request.rerank,
                hybrid_profile=request.hybrid_profile,
            )
    except Exception as exc:  # noqa: BLE001
        raise search_service_error(exc) from exc

    facets_started = perf_counter()
    try:
        facets = search_facets(request.query, filters)
    except Exception:  # noqa: BLE001
        facets = {}
    stage_timings["facets_ms"] = round((perf_counter() - facets_started) * 1000, 1)
    if pagination["enabled"]:
        pagination["has_more"] = bool(
            pagination.get("next_token")
            and request.page * request.limit < facets.get("count", 0)
        )
    total_ms = round((perf_counter() - request_started) * 1000, 1)

    return {
        "query": request.query,
        "mode": request.mode,
        "rerank": request.rerank,
        "hybrid_profile": request.hybrid_profile,
        "execution": execution,
        "filters": filters,
        "pipeline": explain_search_pipeline(
            request.query,
            request.mode,
            filters,
            request.hybrid_profile,
            request.page_token,
            request.limit,
            request.rerank,
        ),
        "facets": facets,
        "features": {
            "synonym_mapping": get_settings().synonym_mapping_name,
            "pagination": pagination["strategy"],
        },
        "pagination": pagination,
        "metrics": {
            "elapsed_ms": total_ms,
            "returned": len(results),
            "requested": request.limit,
            "stages": {**stage_timings, "total_ms": total_ms},
        },
        "results": results,
    }


@app.post("/compare")
def compare(request: SearchRequest):
    try:
        return compare_search_modes(request.query, limit=min(request.limit, 20), filters=request.filters.active())
    except Exception as exc:  # noqa: BLE001
        raise search_service_error(exc) from exc


@app.get("/suggest")
def suggest(q: str = Query(min_length=2, max_length=120), limit: int = Query(default=6, ge=1, le=10)):
    try:
        return {"suggestions": autocomplete(q, limit)}
    except Exception as exc:  # noqa: BLE001
        raise search_service_error(exc) from exc


@app.post("/map-providers")
def map_provider_results(request: SearchRequest):
    try:
        return map_providers(request.filters.active())
    except Exception as exc:  # noqa: BLE001
        raise search_service_error(exc) from exc


@app.get("/filters")
def filters():
    try:
        return available_filters()
    except Exception:
        sample = prepared_sample_documents()
        specialties = {}
        networks = {}
        languages = {}
        for document in sample:
            specialties[document["specialty_name"]] = specialties.get(document["specialty_name"], 0) + 1
            for network in document["insurance_networks"]:
                networks[network] = networks.get(network, 0) + 1
            for language in document["languages"]:
                languages[language] = languages.get(language, 0) + 1
        return {
            "specialties": [{"value": value, "count": count} for value, count in sorted(specialties.items())],
            "networks": [{"value": value, "count": count} for value, count in sorted(networks.items())],
            "languages": [{"value": value, "count": count} for value, count in sorted(languages.items())],
            "origins": [{"value": key, **origin} for key, origin in MAP_ORIGINS.items()],
        }


@app.get("/indexes")
def indexes():
    return index_definitions()


@app.get("/sample-documents")
def sample_documents(limit: int = Query(default=3, ge=1, le=30)):
    return {"documents": prepared_sample_documents()[:limit]}


@app.get("/query-example")
def query_example(
    q: str = Query(default="knee replacement orthopedic surgeon"),
    mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    hybrid_profile: Literal["balanced", "precision", "discovery"] = "balanced",
    limit: int = Query(default=8, ge=1, le=24),
    rerank: bool = False,
):
    return {
        "pipeline": explain_search_pipeline(
            q,
            mode,
            {},
            hybrid_profile,
            limit=limit,
            rerank=rerank,
        )
    }
