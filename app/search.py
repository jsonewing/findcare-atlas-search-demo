from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt
from time import perf_counter
from typing import Any, Literal

from app.config import get_settings
from app.db import get_collection
from app.embeddings import embed_query, rerank_documents
from app.sample_data import MAP_ORIGINS
from app.synonyms import is_known_synonym_phrase


SearchMode = Literal["lexical", "vector", "hybrid"]
HybridProfile = Literal["balanced", "precision", "discovery"]

HYBRID_WEIGHTS: dict[HybridProfile, dict[str, float]] = {
    "balanced": {"lexicalPipeline": 0.55, "vectorPipeline": 0.45},
    "precision": {"lexicalPipeline": 0.75, "vectorPipeline": 0.25},
    "discovery": {"lexicalPipeline": 0.35, "vectorPipeline": 0.65},
}

PROJECT_FIELDS = {
    "_id": {"$toString": "$_id"},
    "provider_id": 1,
    "provider_name": 1,
    "provider_type": 1,
    "specialty_name": 1,
    "specialty_group": 1,
    "aliases": 1,
    "conditions": 1,
    "procedures": 1,
    "splunk_user_keywords": 1,
    "care_summary": 1,
    "insurance_networks": 1,
    "address_line1": 1,
    "phone": 1,
    "next_available": 1,
    "city": 1,
    "state": 1,
    "zip": 1,
    "distance_miles": 1,
    "rating": 1,
    "review_count": 1,
    "accepting_new_patients": 1,
    "telehealth": 1,
    "languages": 1,
    "location": 1,
    "map_label": 1,
}

EARTH_RADIUS_MILES = 3958.8

LEXICAL_MATCH_PATHS = [
    "provider_name",
    "specialty_name",
    "aliases",
    "conditions",
    "procedures",
    "splunk_user_keywords",
    "care_summary",
]
LEXICAL_STOP_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "from", "in", "me", "my", "near", "of", "on", "the", "to", "who", "with"}
)
LEXICAL_OPERATIONAL_TERMS = frozenset(
    {
        "accepting",
        "appointment",
        "appointments",
        "doctor",
        "doctors",
        "new",
        "patient",
        "patients",
        "provider",
        "providers",
        "specialist",
        "specialists",
        "telehealth",
    }
)


def origin_for(filters: dict[str, Any] | None) -> dict[str, Any]:
    filters = filters or {}
    key = filters.get("origin") or "downtown"
    return MAP_ORIGINS.get(key, MAP_ORIGINS["downtown"])


def geo_radius_meters(filters: dict[str, Any] | None) -> float | None:
    filters = filters or {}
    if not filters.get("max_distance"):
        return None
    return float(filters["max_distance"]) * 1609.344


def geo_match(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    radius_meters = geo_radius_meters(filters)
    if not radius_meters:
        return None
    return {
        "location": {
            "$geoWithin": {
                "$centerSphere": [
                    origin_for(filters)["coordinates"],
                    radius_meters / 1000 / 6378.1,
                ]
            }
        }
    }


def distance_miles(point: dict[str, Any] | None, origin: dict[str, Any]) -> float | None:
    if not point or point.get("type") != "Point":
        return None
    lon1, lat1 = point["coordinates"]
    lon2, lat2 = origin["coordinates"]
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * EARTH_RADIUS_MILES * asin(sqrt(a)), 1)


def annotate_geo(results: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    origin = origin_for(filters)
    for result in results:
        result["distance_from_origin_miles"] = distance_miles(result.get("location"), origin)
        result["origin_label"] = origin["label"]
    if (filters or {}).get("sort") == "distance":
        results.sort(key=lambda item: item.get("distance_from_origin_miles") if item.get("distance_from_origin_miles") is not None else 9999)
    return results


def _filter_clauses(filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    filters = filters or {}
    clauses: list[dict[str, Any]] = [
        {"equals": {"path": "document_type", "value": "care_provider"}}
    ]

    if filters.get("specialty"):
        clauses.append({"equals": {"path": "specialty_filter", "value": filters["specialty"]}})
    if filters.get("network"):
        clauses.append({"equals": {"path": "networks_filter", "value": filters["network"]}})
    if filters.get("language"):
        clauses.append({"equals": {"path": "languages_filter", "value": filters["language"]}})
    if filters.get("accepting_new_patients"):
        clauses.append({"equals": {"path": "accepting_new_patients", "value": True}})
    if filters.get("telehealth"):
        clauses.append({"equals": {"path": "telehealth", "value": True}})
    if filters.get("min_rating"):
        clauses.append({"range": {"path": "rating", "gte": float(filters["min_rating"])}})
    radius_meters = geo_radius_meters(filters)
    if radius_meters:
        clauses.append(
            {
                "geoWithin": {
                    "path": "location",
                    "circle": {
                        "center": {
                            "type": "Point",
                            "coordinates": origin_for(filters)["coordinates"],
                        },
                        "radius": radius_meters,
                    },
                }
            }
        )

    return clauses


def _vector_filter(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    filters = filters or {}
    clauses: list[dict[str, Any]] = [
        {"document_type": {"$eq": "care_provider"}},
    ]

    if filters.get("specialty"):
        clauses.append({"specialty_filter": {"$eq": filters["specialty"]}})
    if filters.get("network"):
        clauses.append({"networks_filter": {"$eq": filters["network"]}})
    if filters.get("language"):
        clauses.append({"languages_filter": {"$eq": filters["language"]}})
    if filters.get("accepting_new_patients"):
        clauses.append({"accepting_new_patients": {"$eq": True}})
    if filters.get("telehealth"):
        clauses.append({"telehealth": {"$eq": True}})
    if filters.get("min_rating"):
        clauses.append({"rating": {"$gte": float(filters["min_rating"])}})

    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def hybrid_weights(profile: HybridProfile = "balanced") -> dict[str, float]:
    return HYBRID_WEIGHTS.get(profile, HYBRID_WEIGHTS["balanced"])


def _meaningful_query_terms(query: str) -> list[str]:
    terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if term not in LEXICAL_STOP_WORDS]
    return list(dict.fromkeys(terms))[:8]


def _multi_term_recall_gate(query: str) -> dict[str, Any] | None:
    query_terms = _meaningful_query_terms(query)
    if len(query_terms) < 2 or is_known_synonym_phrase(query):
        return None
    terms = [term for term in query_terms if term not in LEXICAL_OPERATIONAL_TERMS] or query_terms
    minimum_matches = min(3 if 4 <= len(terms) <= 5 else 2, len(terms))
    return {
        "compound": {
            "should": [
                {
                    "text": {
                        "query": term,
                        "path": LEXICAL_MATCH_PATHS,
                        "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                    }
                }
                for term in terms
            ],
            "minimumShouldMatch": minimum_matches,
        }
    }


def _lexical_compound(query: str | None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    compound: dict[str, Any] = {"filter": _filter_clauses(filters)}
    if not query:
        return compound

    settings = get_settings()
    recall_gate = _multi_term_recall_gate(query)
    if recall_gate:
        compound["filter"].append(recall_gate)

    compound["should"] = [
        {
            "phrase": {
                "query": query,
                "path": ["provider_name", "specialty_name", "procedures", "conditions"],
                "slop": 2,
                "score": {"boost": {"value": 8}},
            }
        },
        {
            "text": {
                "query": query,
                "path": ["provider_name", "specialty_name", "aliases"],
                "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                "score": {"boost": {"value": 5}},
            }
        },
        {
            "text": {
                "query": query,
                "path": ["conditions", "procedures", "splunk_user_keywords"],
                "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                "score": {"boost": {"value": 3}},
            }
        },
        {
            "text": {
                "query": query,
                "path": ["specialty_name", "conditions", "procedures", "care_summary"],
                "synonyms": settings.synonym_mapping_name,
                "matchCriteria": "any",
                "score": {"boost": {"value": 2.5}},
            }
        },
        {
            "text": {
                "query": query,
                "path": [
                    "care_summary",
                    "provider_type",
                    "specialty_group",
                    "insurance_networks",
                    "languages",
                    "city",
                ],
                "score": {"boost": {"value": 1.5}},
            }
        },
    ]
    compound["minimumShouldMatch"] = 1
    return compound


def lexical_stage(
    query: str,
    filters: dict[str, Any] | None = None,
    *,
    search_after: str | None = None,
    cursor_sort: bool = False,
) -> dict[str, Any]:
    """
    Build a $search stage for full-text lexical search.

    Uses a five-clause compound query: exact phrase, provider identity,
    clinical terminology, synonym expansion, and contextual summary. A
    non-scoring multi-term gate prevents a generic token such as "surgery"
    from admitting unrelated specialties. Autocomplete runs independently.

    Atlas Search automatically ranks results using BM25 relevance scoring, which:
    - Normalizes for document length
    - Applies term frequency and inverse document frequency
    - Boosts term importance based on score weights

    Filters apply as MUST constraints (all must match for inclusion).
    """
    settings = get_settings()
    search: dict[str, Any] = {
        "index": settings.search_index_name,
        "compound": _lexical_compound(query, filters),
        "highlight": {
            "path": ["provider_name", "specialty_name", "conditions", "procedures", "care_summary"]
        },
    }
    if cursor_sort:
        search["sort"] = {"score": {"$meta": "searchScore"}, "provider_id": 1}
    if search_after:
        search["searchAfter"] = search_after
    return {"$search": search}


def search_facets(query: str | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return Atlas Search facet buckets and an exact matching-provider count."""
    settings = get_settings()
    pipeline = [
        {
            "$searchMeta": {
                "index": settings.search_index_name,
                "facet": {
                    "operator": {"compound": _lexical_compound(query, filters)},
                    "facets": {
                        "specialties": {"type": "string", "path": "specialty_filter", "numBuckets": 100},
                        "networks": {"type": "string", "path": "networks_filter", "numBuckets": 50},
                        "languages": {"type": "string", "path": "languages_filter", "numBuckets": 50},
                    },
                },
                "count": {"type": "total"},
            }
        }
    ]
    metadata = next(iter(get_collection().aggregate(pipeline)), {})
    facet_metadata = metadata.get("facet", {})

    def options(name: str) -> list[dict[str, Any]]:
        return [
            {"value": bucket["_id"], "count": bucket["count"]}
            for bucket in facet_metadata.get(name, {}).get("buckets", [])
        ]

    return {
        "count": metadata.get("count", {}).get("total", 0),
        "specialties": options("specialties"),
        "networks": options("networks"),
        "languages": options("languages"),
    }


def available_filters() -> dict[str, Any]:
    facets = search_facets()
    return {
        **facets,
        "origins": [{"value": key, **origin} for key, origin in MAP_ORIGINS.items()],
    }


def vector_stage(
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
    query_vector: list[float] | list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a $vectorSearch stage for semantic/vector search.

    Vector search finds semantically similar care providers by:
    1. Converting the query to embeddings using Voyage AI (1024-dim model)
       - Embeddings capture semantic meaning beyond keywords
       - Example: "knee pain" and "ACL injury" map to similar vectors

    2. Using cosine similarity to find nearest neighbors
       - numCandidates: at least 20x the requested result window
       - Higher candidates = more recall but slower performance
       - Smaller limit = faster results, fewer candidates

    3. Applying pre-filter constraints if specified
       - Filters use MongoDB query syntax (not $search syntax)
       - Examples: { specialty_filter: "orthopedics" }, { rating: { $gte: 4.5 } }
       - Pre-filtering before vector search improves recall by narrowing candidate set

    4. Using scalar quantization for efficiency
       - Reduces embedding vector size without significantly impacting quality
       - Trades <1% accuracy for better performance and memory usage

    Returns top N results ranked by cosine similarity score.
    """
    settings = get_settings()
    stage: dict[str, Any] = {
        "$vectorSearch": {
            "index": settings.vector_index_name,
            "path": "embedding",
            "queryVector": query_vector if query_vector is not None else embed_query(query),
            "numCandidates": min(10000, max(100, limit * 20)),
            "limit": limit,
        }
    }
    vector_filter = _vector_filter(filters)
    if vector_filter:
        stage["$vectorSearch"]["filter"] = vector_filter
    return stage


def lexical_search(query: str, limit: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    pipeline = [
        lexical_stage(query, filters),
        {"$limit": limit},
        {
            "$project": {
                **PROJECT_FIELDS,
                "score": {"$meta": "searchScore"},
                "highlights": {"$meta": "searchHighlights"},
                "score_type": "searchScore",
            }
        },
    ]
    return annotate_geo(list(get_collection().aggregate(pipeline)), filters)


def lexical_search_page(
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
    search_after: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    pipeline = [
        lexical_stage(query, filters, search_after=search_after, cursor_sort=True),
        {"$limit": limit},
        {
            "$project": {
                **PROJECT_FIELDS,
                "score": {"$meta": "searchScore"},
                "highlights": {"$meta": "searchHighlights"},
                "pagination_token": {"$meta": "searchSequenceToken"},
                "score_type": "searchScore",
            }
        },
    ]
    results = annotate_geo(list(get_collection().aggregate(pipeline)), filters)
    next_token = results[-1].get("pagination_token") if len(results) == limit else None
    return results, next_token


def vector_search(
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
    query_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    pipeline = [
        vector_stage(query, limit, filters, query_vector=query_vector),
        *([{"$match": geo_match(filters)}] if geo_match(filters) else []),
        {"$project": {**PROJECT_FIELDS, "score": {"$meta": "vectorSearchScore"}, "score_type": "vectorSearchScore"}},
    ]
    return annotate_geo(list(get_collection().aggregate(pipeline)), filters)


def _normalize_fusion_details(result: dict[str, Any]) -> dict[str, Any]:
    score_details = result.pop("score_details", None) or {}
    fusion: dict[str, Any] = {}
    for detail in score_details.get("details", []):
        pipeline_name = detail.get("inputPipelineName", "").removesuffix("Pipeline")
        if not pipeline_name:
            continue
        rank = detail.get("rank")
        weight = detail.get("weight")
        if not isinstance(rank, int) or not isinstance(weight, (int, float)):
            continue
        fusion[pipeline_name] = {
            "rank": rank,
            "score": detail.get("value"),
            "weight": weight,
            "contribution": weight * (1 / (60 + rank)),
        }
    result["score"] = score_details.get("value")
    result["score_type"] = "scoreDetails"
    result["fusion"] = fusion
    result["score_details"] = score_details
    return result


def atlas_rank_fusion_search(
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
    profile: HybridProfile = "balanced",
    query_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid search using MongoDB Atlas $rankFusion (requires MongoDB 8.0+).

    Combines lexical and vector search via Reciprocal Rank Fusion (RRF):

    1. Executes two bounded input pipelines in Atlas:
       - Lexical: Full-text search for keyword matching (BM25 scoring)
       - Vector: Semantic search for conceptual similarity (cosine similarity)

    2. Applies RRF formula to blend results:
       - Balanced RRF = 55% lexical + 45% vector
       - Precision and discovery profiles can shift those weights per query
       - Why RRF? It's robust and doesn't require score normalization
       - Constant 60: Prevents low-ranked items from scoring too high

    3. Returns scoreDetails metadata showing:
       - fusion.lexical: rank, score, contribution from text search
       - fusion.vector: rank, score, contribution from semantic search
       - This transparency helps understand why a result ranked highly

    Compared to client-side fusion:
    - Faster: Executes in MongoDB, not in application
    - Cleaner: Single aggregation pipeline vs multiple queries
    - Native: Uses MongoDB's optimized RRF implementation
    """
    pipeline_limit = max(50, limit * 5)
    vector_pipeline = [vector_stage(query, pipeline_limit, filters, query_vector=query_vector)]
    if geo_match(filters):
        vector_pipeline.append({"$match": geo_match(filters)})
    pipeline = [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "lexicalPipeline": [lexical_stage(query, filters), {"$limit": pipeline_limit}],
                        "vectorPipeline": vector_pipeline,
                    }
                },
                "combination": {"weights": hybrid_weights(profile)},
                "scoreDetails": True,
            }
        },
        {"$limit": limit},
        {"$project": {**PROJECT_FIELDS, "score_details": {"$meta": "scoreDetails"}}},
    ]
    results = [_normalize_fusion_details(result) for result in get_collection().aggregate(pipeline)]
    return annotate_geo(results, filters)


def client_rank_fusion_search(
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
    profile: HybridProfile = "balanced",
    query_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid search using client-side Reciprocal Rank Fusion (fallback for MongoDB <8.0).

    When $rankFusion is unavailable, performs RRF in application code:

    1. Executes two separate queries:
       - Lexical search pipeline via $search
       - Vector search pipeline via $vectorSearch

    2. Merges results using RRF algorithm:
       - Fetches candidate_limit (limit * 4) from each pipeline
       - Combines by document ID, summing weighted contributions
       - RRF formula: profile weight * (1/(60+rank)) for each result list

    3. Returns fused results with breakdown:
       - fusion.lexical: Original rank and score from text search
       - fusion.vector: Original rank and score from semantic search
       - score: Combined RRF score for final ranking

    Tradeoffs vs server-side $rankFusion:
    - Pro: Works on older MongoDB versions
    - Con: Two network round-trips instead of one
    - Con: Application-level processing (not optimized in database)
    - Note: Results should be nearly identical to $rankFusion
    """
    candidate_limit = max(25, limit * 4)
    lexical_results = lexical_search(query, candidate_limit, filters)
    vector_results = vector_search(query, candidate_limit, filters, query_vector=query_vector)
    fused: dict[str, dict[str, Any]] = {}

    weights = hybrid_weights(profile)

    def add(results: list[dict[str, Any]], pipeline_name: str, weight: float) -> None:
        for rank, result in enumerate(results, start=1):
            doc_id = result["_id"]
            item = fused.setdefault(doc_id, {**result, "fusion": {}, "score": 0.0, "score_type": "clientRRF"})
            contribution = weight * (1 / (60 + rank))
            item["score"] += contribution
            item["fusion"][pipeline_name] = {
                "rank": rank,
                "score": result.get("score"),
                "weight": weight,
                "contribution": contribution,
            }

    add(lexical_results, "lexical", weights["lexicalPipeline"])
    add(vector_results, "vector", weights["vectorPipeline"])
    return annotate_geo(sorted(fused.values(), key=lambda item: item["score"], reverse=True)[:limit], filters)


def autocomplete(query: str, limit: int = 6) -> list[dict[str, Any]]:
    pipeline = [
        {
            "$search": {
                "index": get_settings().search_index_name,
                "compound": {
                    "must": [
                        {
                            "autocomplete": {
                                "query": query,
                                "path": "autocomplete_text",
                                "tokenOrder": "sequential",
                                "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                            }
                        }
                    ],
                    "filter": [{"equals": {"path": "document_type", "value": "care_provider"}}],
                },
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "provider_name": 1,
                "specialty_name": 1,
                "city": 1,
                "state": 1,
                "score": {"$meta": "searchScore"},
            }
        },
    ]
    return list(get_collection().aggregate(pipeline))


def search_providers_with_metrics(
    query: str,
    mode: SearchMode,
    limit: int = 8,
    filters: dict[str, Any] | None = None,
    rerank: bool = False,
    hybrid_profile: HybridProfile = "balanced",
) -> tuple[list[dict[str, Any]], str, dict[str, float]]:
    timings = {"embedding_ms": 0.0, "retrieval_ms": 0.0, "rerank_ms": 0.0}
    candidate_limit = max(limit, 20) if rerank else limit
    query_vector = None

    if mode in ("vector", "hybrid"):
        started = perf_counter()
        query_vector = embed_query(query)
        timings["embedding_ms"] = round((perf_counter() - started) * 1000, 1)

    started = perf_counter()
    if mode == "vector":
        results = vector_search(query, candidate_limit, filters, query_vector=query_vector)
        execution = "$vectorSearch"
    elif mode == "lexical":
        results = lexical_search(query, candidate_limit, filters)
        execution = "$search"
    else:
        settings = get_settings()
        if settings.use_atlas_rank_fusion:
            results = atlas_rank_fusion_search(
                query,
                candidate_limit,
                filters,
                hybrid_profile,
                query_vector=query_vector,
            )
            execution = "$rankFusion"
        else:
            results = client_rank_fusion_search(
                query,
                candidate_limit,
                filters,
                hybrid_profile,
                query_vector=query_vector,
            )
            execution = "client-side RRF fallback"
    timings["retrieval_ms"] = round((perf_counter() - started) * 1000, 1)

    if rerank and results:
        started = perf_counter()
        documents = [rerank_text(result) for result in results]
        reranked = rerank_documents(query, documents, top_k=min(limit, len(documents)))
        ranked_results = []
        for rank, item in enumerate(reranked, start=1):
            result = dict(results[item.index])
            result["original_rank"] = item.index + 1
            result["rerank_score"] = item.relevance_score
            result["reranked"] = True
            ranked_results.append(result)
        timings["rerank_ms"] = round((perf_counter() - started) * 1000, 1)
        return annotate_geo(ranked_results, filters), f"{execution} + Voyage rerank", timings

    for rank, result in enumerate(results[:limit], start=1):
        result["original_rank"] = rank
        result["reranked"] = False
    return annotate_geo(results[:limit], filters), execution, timings


def search_providers(
    query: str,
    mode: SearchMode,
    limit: int = 8,
    filters: dict[str, Any] | None = None,
    rerank: bool = False,
    hybrid_profile: HybridProfile = "balanced",
) -> tuple[list[dict[str, Any]], str]:
    results, execution, _ = search_providers_with_metrics(
        query,
        mode,
        limit,
        filters,
        rerank,
        hybrid_profile,
    )
    return results, execution


def compare_search_modes(
    query: str,
    limit: int = 6,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_vector = embed_query(query)
    settings = get_settings()
    mode_results: tuple[tuple[SearchMode, str, list[dict[str, Any]]], ...] = (
        ("lexical", "$search", lexical_search(query, limit, filters)),
        ("vector", "$vectorSearch", vector_search(query, limit, filters, query_vector=query_vector)),
        (
            "hybrid",
            "$rankFusion" if settings.use_atlas_rank_fusion else "client-side RRF fallback",
            (
                atlas_rank_fusion_search(query, limit, filters, query_vector=query_vector)
                if settings.use_atlas_rank_fusion
                else client_rank_fusion_search(query, limit, filters, query_vector=query_vector)
            ),
        ),
    )
    modes: tuple[SearchMode, ...] = tuple(item[0] for item in mode_results)
    comparison: list[dict[str, Any]] = []
    for mode, execution, results in mode_results:
        comparison.append(
            {
                "mode": mode,
                "execution": execution,
                "results": [
                    {
                        "provider_id": result["provider_id"],
                        "provider_name": result["provider_name"],
                        "specialty_name": result["specialty_name"],
                        "distance_miles": result["distance_miles"],
                        "distance_from_origin_miles": result.get("distance_from_origin_miles"),
                        "rating": result["rating"],
                        "score_type": result.get("score_type"),
                        "score": result.get("score"),
                        "fusion": result.get("fusion"),
                        "rank": rank,
                    }
                    for rank, result in enumerate(results, start=1)
                ],
            }
        )

    rank_maps = {
        item["mode"]: {result["provider_id"]: result["rank"] for result in item["results"]}
        for item in comparison
    }
    all_ids = set().union(*(set(ranks) for ranks in rank_maps.values()))
    for item in comparison:
        for result in item["results"]:
            result["ranks"] = {
                mode: rank_maps[mode].get(result["provider_id"])
                for mode in modes
            }

    shared_ids = set(rank_maps["lexical"]) & set(rank_maps["vector"]) & set(rank_maps["hybrid"])
    return {
        "query": query,
        "filters": filters or {},
        "limit": limit,
        "summary": {
            "unique_results": len(all_ids),
            "shared_all_modes": len(shared_ids),
            "lexical_vector_overlap": len(set(rank_maps["lexical"]) & set(rank_maps["vector"])),
        },
        "comparison": comparison,
    }


def map_providers(filters: dict[str, Any] | None = None, limit: int = 60) -> dict[str, Any]:
    query_filter: dict[str, Any] = {"document_type": "care_provider"}
    if geo_match(filters):
        query_filter.update(geo_match(filters) or {})
    projection = {
        "_id": 0,
        "provider_id": 1,
        "provider_name": 1,
        "specialty_name": 1,
        "city": 1,
        "state": 1,
        "zip": 1,
        "location": 1,
        "rating": 1,
        "accepting_new_patients": 1,
        "telehealth": 1,
    }
    providers = annotate_geo(list(get_collection().find(query_filter, projection).limit(limit)), filters)
    return {"origin": origin_for(filters), "providers": providers}


def rerank_text(result: dict[str, Any]) -> str:
    return (
        f"{result.get('provider_name', '')}. {result.get('specialty_name', '')}. "
        f"{result.get('care_summary', '')} Conditions: {', '.join(result.get('conditions', []))}. "
        f"Procedures: {', '.join(result.get('procedures', []))}. "
        f"Keywords: {', '.join(result.get('splunk_user_keywords', []))}."
    )


def explain_search_pipeline(
    query: str,
    mode: SearchMode,
    filters: dict[str, Any] | None = None,
    hybrid_profile: HybridProfile = "balanced",
    page_token: str | None = None,
    limit: int = 8,
    rerank: bool = False,
) -> list[dict[str, Any]]:
    candidate_limit = max(limit, 20) if rerank else limit
    if mode == "vector":
        stage = vector_stage(query, candidate_limit, filters, query_vector=["<Voyage query embedding>"])
        return [
            stage,
            *([{"$match": geo_match(filters)}] if geo_match(filters) else []),
            {"$project": {**PROJECT_FIELDS, "score": {"$meta": "vectorSearchScore"}}},
        ]
    if mode == "lexical":
        if rerank:
            return [
                lexical_stage(query, filters),
                {"$limit": candidate_limit},
                {
                    "$project": {
                        **PROJECT_FIELDS,
                        "score": {"$meta": "searchScore"},
                        "highlights": {"$meta": "searchHighlights"},
                    }
                },
            ]
        return [
            lexical_stage(query, filters, search_after=page_token, cursor_sort=True),
            {"$limit": limit},
            {
                "$project": {
                    **PROJECT_FIELDS,
                    "score": {"$meta": "searchScore"},
                    "highlights": {"$meta": "searchHighlights"},
                    "pagination_token": {"$meta": "searchSequenceToken"},
                }
            },
        ]

    pipeline_limit = max(50, candidate_limit * 5)
    vector = vector_stage(query, pipeline_limit, filters, query_vector=["<Voyage query embedding>"])
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "lexicalPipeline": [
                            lexical_stage(query, filters),
                            {"$limit": pipeline_limit},
                        ],
                        "vectorPipeline": [
                            vector,
                            *([{"$match": geo_match(filters)}] if geo_match(filters) else []),
                        ],
                    }
                },
                "combination": {"weights": hybrid_weights(hybrid_profile)},
                "scoreDetails": True,
            }
        },
        {"$limit": candidate_limit},
        {"$project": {**PROJECT_FIELDS, "score_details": {"$meta": "scoreDetails"}}},
    ]
