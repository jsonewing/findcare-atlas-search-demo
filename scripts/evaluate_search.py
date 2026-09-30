from __future__ import annotations

from dataclasses import dataclass

from app.search import search_providers


@dataclass(frozen=True)
class Scenario:
    name: str
    query: str
    mode: str
    expected_specialties: frozenset[str]
    top_k: int = 3
    filters: dict | None = None
    hybrid_profile: str = "balanced"
    rerank: bool = False
    required_matches: int = 1


SCENARIOS = (
    Scenario(
        "Typo tolerance",
        "orthapedic knee replacment",
        "lexical",
        frozenset({"Orthopedic Surgery"}),
        required_matches=3,
    ),
    Scenario(
        "Exact procedure precision",
        "knee replacement orthopedic surgeon",
        "lexical",
        frozenset({"Orthopedic Surgery"}),
        required_matches=3,
    ),
    Scenario(
        "Medical synonym expansion",
        "otolaryngologist",
        "lexical",
        frozenset({"Otolaryngology"}),
        required_matches=3,
    ),
    Scenario(
        "Natural-language sports injury",
        "doctor who treats torn ACL after soccer injury",
        "hybrid",
        frozenset({"Orthopedic Surgery", "Sports Medicine"}),
        hybrid_profile="discovery",
        required_matches=2,
    ),
    Scenario(
        "Imaging intent",
        "MRI for joint injury",
        "hybrid",
        frozenset({"Radiology"}),
        required_matches=2,
    ),
    Scenario(
        "Semantic symptom recall",
        "help breathing while asleep",
        "vector",
        frozenset({"Sleep Medicine", "Pulmonology"}),
        required_matches=3,
    ),
    Scenario(
        "Intent disambiguation",
        "stomach pain after eating specialist",
        "vector",
        frozenset({"Gastroenterology"}),
    ),
    Scenario(
        "Operational prefilters",
        "heart doctor telehealth",
        "hybrid",
        frozenset({"Cardiology", "Cardiothoracic Surgery"}),
        filters={"telehealth": True, "accepting_new_patients": True},
        required_matches=2,
    ),
    Scenario(
        "Voyage final reranking",
        "anxiety medication management",
        "hybrid",
        frozenset({"Psychiatry"}),
        rerank=True,
        required_matches=3,
    ),
)

EXPECTED_WEIGHTS = {
    "balanced": {"lexical": 0.55, "vector": 0.45},
    "precision": {"lexical": 0.75, "vector": 0.25},
    "discovery": {"lexical": 0.35, "vector": 0.65},
}


def main() -> None:
    failures: list[str] = []
    print("FindCare relevance evaluation")

    for scenario in SCENARIOS:
        results, execution = search_providers(
            scenario.query,
            scenario.mode,  # type: ignore[arg-type]
            limit=max(5, scenario.top_k),
            filters=scenario.filters,
            rerank=scenario.rerank,
            hybrid_profile=scenario.hybrid_profile,  # type: ignore[arg-type]
        )
        top_results = results[: scenario.top_k]
        matched_count = sum(
            result.get("specialty_name") in scenario.expected_specialties
            for result in top_results
        )
        filters_hold = all(
            (not scenario.filters or not scenario.filters.get("telehealth") or result.get("telehealth"))
            and (
                not scenario.filters
                or not scenario.filters.get("accepting_new_patients")
                or result.get("accepting_new_patients")
            )
            for result in results
        )
        execution_holds = not scenario.rerank or execution.endswith("+ Voyage rerank")
        passed = bool(results) and matched_count >= scenario.required_matches and filters_hold and execution_holds
        status = "PASS" if passed else "FAIL"
        names = [f"{item['provider_name']} ({item['specialty_name']})" for item in top_results]
        print(f"[{status}] {scenario.name}: {execution}")
        print(f"       {scenario.query!r} -> {names}")
        if not passed:
            failures.append(scenario.name)

    if failures:
        raise SystemExit(f"Relevance checks failed: {', '.join(failures)}")

    print("\nNative rank-fusion score verification")
    for profile, expected_weights in EXPECTED_WEIGHTS.items():
        results, execution = search_providers(
            "doctor who treats torn ACL after soccer injury",
            "hybrid",
            limit=8,
            hybrid_profile=profile,  # type: ignore[arg-type]
        )
        if execution != "$rankFusion":
            failures.append(f"{profile} did not execute $rankFusion")
            continue

        maximum_delta = 0.0
        for result in results:
            fusion = result.get("fusion", {})
            calculated = 0.0
            for lane, detail in fusion.items():
                expected_weight = expected_weights[lane]
                if abs(detail["weight"] - expected_weight) > 1e-12:
                    failures.append(f"{profile} {lane} weight")
                expected_contribution = expected_weight / (60 + detail["rank"])
                maximum_delta = max(maximum_delta, abs(detail["contribution"] - expected_contribution))
                calculated += expected_contribution
            maximum_delta = max(maximum_delta, abs(result["score"] - calculated))

        passed = bool(results) and maximum_delta < 1e-12
        print(f"[{'PASS' if passed else 'FAIL'}] {profile:9} weights and RRF math · max delta {maximum_delta:.2e}")
        if not passed:
            failures.append(f"{profile} RRF score")

    if failures:
        raise SystemExit(f"Evaluation checks failed: {', '.join(failures)}")

    print(f"\nAll {len(SCENARIOS)} relevance checks and 3 fusion profiles passed.")


if __name__ == "__main__":
    main()
