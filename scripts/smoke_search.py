from __future__ import annotations

from app.config import get_settings
from app.search import compare_search_modes, lexical_search_page, search_facets, search_providers


QUERIES = [
    "knee replacement orthopedic surgeon",
    "rash doctor accepting new patients",
    "heart doctor telehealth",
    "same day clinic sore throat",
    "MRI for joint injury",
    "doctor who treats torn ACL after soccer injury",
    "otolaryngologist",
]


def names(results: list[dict]) -> list[str]:
    return [result["provider_name"] for result in results[:3]]


def main() -> None:
    settings = get_settings()
    print(f"Collection: {settings.atlas_db}.{settings.atlas_collection}")
    print(f"Atlas rankFusion enabled: {settings.use_atlas_rank_fusion}")

    for query in QUERIES:
        print(f"\nQuery: {query}")
        for mode in ("lexical", "vector", "hybrid"):
            results, execution = search_providers(query, mode, limit=3)
            assert all(result.get("provider_id") for result in results), "Non-provider document leaked into results"
            print(f"- {mode:7} {execution:24} {names(results)}")

    comparison = compare_search_modes(QUERIES[-1], limit=6)
    print("\nMode comparison:")
    print(f"- {comparison['summary']}")

    facets = search_facets("knee replacement orthopedic surgeon")
    print("\nAtlas Search facets:")
    print(f"- matches={facets['count']} specialties={facets['specialties'][:3]}")

    page_one, next_token = lexical_search_page("doctor", limit=3)
    assert next_token, "Atlas Search did not return a pagination token"
    page_two, _ = lexical_search_page("doctor", limit=3, search_after=next_token)
    assert {item["provider_id"] for item in page_one}.isdisjoint(
        {item["provider_id"] for item in page_two}
    ), "Cursor pagination repeated a provider"
    print("\nCursor pagination:")
    print(f"- page 1 {names(page_one)}")
    print(f"- page 2 {names(page_two)}")

    results, execution = search_providers(
        "rash specialist accepting new patients",
        "hybrid",
        limit=3,
        filters={"origin": "downtown", "max_distance": 10, "sort": "distance"},
    )
    print("\nGeo check:")
    print(f"- hybrid  {execution:24} {[(r['provider_name'], r.get('distance_from_origin_miles')) for r in results]}")

    results, execution = search_providers(
        "doctor who treats torn ACL after soccer injury",
        "hybrid",
        limit=3,
        rerank=True,
    )
    print("\nRerank check:")
    print(f"- hybrid  {execution:24} {names(results)}")


if __name__ == "__main__":
    main()
