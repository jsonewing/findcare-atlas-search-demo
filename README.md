# FindCare Atlas Search Demo

This demo shows how MongoDB Atlas can centralize a healthcare search experience like a FindCare portal. One provider document supports Atlas Search full-text relevance, Atlas Vector Search semantic retrieval, hybrid search with `$rankFusion`, and optional Voyage reranking.

> **Synthetic demo notice:** All provider records and network participation are fictional. Third-party trademarks belong to their respective owners; no affiliation or endorsement is implied. This project demonstrates search technology and does not provide medical advice.

The UI is intentionally focused: search for a condition, procedure, specialty, symptom, or provider; apply common filters; switch between full-text, vector, and hybrid modes; then inspect the exact query pipeline, native score details, sample documents, or either index definition.

## Portable Launch

The canonical launcher is now self-contained:

```bash
./run.sh
```

On macOS, `start.command` is double-clickable. The first launch downloads and SHA-256 verifies pinned Python 3.12.13 into `vendor/`, creates a project-local `.venv`, installs pinned dependencies, waits for `http://127.0.0.1:8035/ready`, and then opens the browser. Use `PORT=<port> ./run.sh` to select another loopback port. The browser provides first-run Atlas and Voyage credential setup and can install the ZIP's 100-provider synthetic corpus, synonym mappings, and missing indexes into an empty namespace. Secrets are saved only to a permission-restricted local `.env`.

See `PORTABLE_README.md` for packaging, restart, checksum, and clean-install verification instructions.

## What It Builds

- `app/sample_data.py` defines sample healthcare provider, facility, specialty, procedure, condition, network, and location documents.
- `scripts/seed_findcare.py` embeds those documents with Voyage `voyage-4`, loads them into Atlas, and seeds a dedicated medical synonym source collection.
- `indexes/search_index.json` defines the Atlas Search index for full text, phrase, autocomplete, synonyms, facets, filters, stable cursor pagination, and geo.
- `indexes/vector_index.json` defines the Atlas Vector Search index over `embedding` with filter fields.
- `app/search.py` contains tuned `$search`, `$vectorSearch`, native `$rankFusion`, `$searchMeta` facets, a client-side RRF fallback, autocomplete, geo filtering, and Voyage rerank logic.
- `static/` contains the member-facing browser portal, visible autocomplete, interactive facets, result evidence, lexical cursor pagination, stage timing, visual rank comparison, interactive geo map pins, score education, and a tabbed search-architecture infographic.

## Prerequisites

- MongoDB Atlas cluster with Atlas Search and Vector Search.
- MongoDB 8.0+ if you want Atlas-native `$rankFusion`.
- Voyage API key.
- Python 3.11 or newer.

## Setup

```bash
make setup
cp .env.example .env
```

Edit `.env`:

```bash
ATLAS_URI=mongodb+srv://...
ATLAS_DB=findcare_demo
ATLAS_COLLECTION=care_providers

VOYAGE_API_KEY=...
VOYAGE_EMBED_MODEL=voyage-4
VOYAGE_EMBED_DIMENSIONS=1024
VOYAGE_RERANK_MODEL=rerank-2

VECTOR_INDEX_NAME=vector_index
SEARCH_INDEX_NAME=search_index
SYNONYM_COLLECTION=medical_synonyms
SYNONYM_MAPPING_NAME=medical_synonyms
USE_ATLAS_RANK_FUSION=true
```

Set `USE_ATLAS_RANK_FUSION=false` if the cluster is not on MongoDB 8.0+. The app will still demonstrate hybrid search with the same reciprocal rank fusion formula in application code.

## Load Data And Indexes

Seed sample provider documents with Voyage embeddings and the medical synonym source:

```bash
make seed
```

To refresh only the synonym source without regenerating embeddings:

```bash
make synonyms
```

Create both Atlas Search indexes:

```bash
make indexes
```

Atlas can take a few minutes to finish building the indexes.

## Validate The Demo

```bash
make test       # local pipeline/index contract tests and JavaScript syntax
make smoke      # live Atlas search, facets, geo, rank fusion, and rerank checks
make evaluate   # relevance assertions plus native RRF weight/math verification
```

`make evaluate` exits nonzero when a curated scenario fails. It also checks Balanced, Lexical-first, and Semantic-first profiles against Atlas's `weight * (1 / (60 + rank))` calculation to confirm the displayed fusion contributions match the native score.

## Run The Demo

```bash
./run.sh
```

Open `http://127.0.0.1:8035`. `make run` invokes the same portable launcher.

## Scenario Matrix

| Query | Start with | What it demonstrates |
| --- | --- | --- |
| `orthapedic knee replacment` | Full text | Fuzzy typo tolerance and high-value field boosts |
| `otolaryngologist` | Full text | Atlas synonym expansion from member terminology to indexed clinical terminology |
| `knee replacement orthopedic surgeon` | Full text, then Hybrid | Exact phrase/procedure precision plus semantic recall |
| `doctor who treats torn ACL after soccer injury` | Compare modes | Natural-language intent and rank movement across all three pipelines |
| `heart doctor telehealth` | Hybrid | Alias matching, semantic intent, and boolean filtering |
| `MRI for joint injury` | Compare modes | Procedure terminology versus semantically related imaging care |
| `help breathing while asleep` | Vector | Semantic symptom recall without exact specialty terminology |
| `stomach pain after eating specialist` | Vector, then Compare modes | Intent disambiguation toward gastroenterology |
| `anxiety medication management` | Hybrid + rerank | Multi-stage retrieval and final Voyage relevance ordering |

Each `Try a scenario` preset resets the demo to Downtown Austin, relevance sort, 12 results, cleared facets, and a known blend/rerank state before executing. This keeps presenter outcomes deterministic even after an audience-driven filter or mode change.

## Demo Flow

1. Start in `Hybrid` with `knee replacement orthopedic surgeon`. The result cards show both lexical and semantic source ranks from Atlas-native `scoreDetails`.
2. Open `Compare modes`. The selected 8, 12, or 20 result window is used in every lane, making overlap, unique recall, and rank movement visible without reading raw JSON.
3. Type `ort` slowly and select a result from the visible Atlas autocomplete menu. Then select `Typo tolerance` to show fuzzy text matching and field-specific boosts.
4. Select `Medical synonym`. Open `Why this matched`, `Query pipeline`, and `Search index` to connect the live result to the `medical_synonyms` mapping.
5. Select `Sports injury intent` or `Symptom recall`. Each preset chooses the retrieval strategy tuned for that scenario, while `Compare modes` shows how Voyage embeddings recover conceptually related providers without relying on every exact term.
6. Return to `Hybrid` and change `Hybrid blend` between Balanced, Lexical first, and Semantic first. Open `Query pipeline` to show the corresponding weights inside `$rankFusion`.
7. Expand `Score details` and `Why this matched` on a result. Atlas reports source ranks and RRF contributions while the evidence panel distinguishes lexical highlights from semantic context.
8. Click the `?` beside `Atlas facets` to explain `$searchMeta`, then select a specialty chip and expand `Filters` to add network, language, rating, availability, or telehealth constraints.
9. Switch to `Full text` and use `Next` to demonstrate `searchSequenceToken` pagination with stable relevance and provider-ID sorting.
10. Read the execution trace from left to right: Voyage embedding, Atlas retrieval, `$searchMeta` facets, optional rerank, and total server time.
11. Change `Origin`, `Distance`, and `Sort`. Full-text geo filtering runs as Atlas Search `geoWithin`; vector candidates use the existing `2dsphere` pattern before presentation.
12. Enable `Voyage rerank`. The UI preserves the Atlas retrieval rank and shows the final rerank score, making retrieval and reranking distinct stages.
13. Open `Search index` and `Vector index`. Each has a compact implementation summary above the complete live JSON definition.
14. Open `Architecture` and move through Overview, Full Text, Vector, Hybrid, and Rerank. Use the `?` beside Score Breakdown to explain why the score types should be interpreted separately.

## Presenter Runbooks

### Five-Minute Flow

1. Start with `knee replacement orthopedic surgeon` in Hybrid and frame the single provider document as the operational and search source of truth.
2. Open `Compare modes` to show keyword precision, semantic recall, and native `$rankFusion` ordering.
3. Run `Medical synonym`, then open `Why this matched` to show synonym-aware lexical retrieval.
4. Apply a clickable specialty facet and a telehealth filter to show indexed, non-scoring constraints.
5. Enable Voyage rerank, review the stage timings, and finish with the Architecture overview.

### Fifteen-Minute Flow

1. Follow the five-minute flow, then demonstrate autocomplete with `ort` and typo tolerance with `orthapedic knee replacment`.
2. Use `Sports injury intent` with each hybrid blend to explain query-dependent weighting.
3. Expand Score Breakdown and calculate the top result's weighted RRF contributions.
4. Switch to Full text and page forward with the Atlas continuation token.
5. Apply origin and radius filters, select a map pin, and open `Geo query`.
6. Inspect both index definitions and the current aggregation pipeline.
7. Run `make evaluate` and use its scenario assertions as the bridge to production relevance evaluation.

## Expected Scenario Changes

| Scenario | What should be visible |
| --- | --- |
| Typo tolerance | Orthopedic providers remain near the top despite both misspelled words. |
| Medical synonym | Otolaryngology providers rank for `otolaryngologist`, with the synonym mapping visible in the query and index dialogs. |
| Procedure precision | Full text favors providers that explicitly contain knee replacement and orthopedic terminology. |
| Sports injury intent | Vector and Hybrid recover sports medicine and orthopedic providers even when wording differs. |
| Imaging intent | Hybrid balances the exact `MRI` procedure with semantically related injury-imaging providers. |
| Symptom recall | Vector maps conversational breathing and sleep language to Sleep Medicine and Pulmonology. |
| Care constraints | Every returned result satisfies accepting-patient and telehealth filters before presentation. |
| Voyage rerank | Final ordering can change while each card preserves the original Atlas retrieval rank. |

## Score Interpretation

| Label | Meaning | Presenter caution |
| --- | --- | --- |
| Search | Atlas Search lexical relevance based on term statistics, boosts, phrase proximity, fuzzy matches, and synonyms. | It has no fixed range; compare only within the same query and pipeline. |
| Vector | Atlas Vector Search cosine score, reported as `(1 + cosine) / 2`. | Similarity is not a probability or a clinical confidence score. |
| RRF | Weighted reciprocal-rank contribution summed across retrieval lanes. | RRF compares rank positions, not raw Search and Vector scores. |
| Rerank | Voyage query-to-document relevance used to reorder the Atlas candidate set. | It does not replace retrieval, filtering, governance, or the source document. |

## Relevance Tuning Checklist

- Maintain a labeled query set with expected specialties and providers, including misspellings, consumer terms, ambiguous symptoms, and no-result cases.
- Measure Recall@K, MRR, NDCG, zero-result rate, click-through, appointment conversion, and p50/p95 latency.
- Tune phrase and field boosts before adding more clauses; keep non-scoring constraints in `compound.filter` or `$vectorSearch.filter`.
- Tune Hybrid weights by query class. Known names and procedures usually favor lexical retrieval; symptom narratives usually favor semantic retrieval.
- Evaluate `numCandidates` against recall and latency. The demo starts at roughly 20 times the requested result window.
- Keep rerank depth bounded and compare reranked quality against the Atlas-only baseline.
- Review synonym changes with clinical/domain owners. Synonym-source updates do not require rebuilding the Search index.
- Re-run `make evaluate` after changing boosts, weights, analyzers, embeddings, synonyms, or candidate windows.

## Production Readiness

- **Index sizing:** Validate Search and Vector index memory, partitions, and search-node capacity against production cardinality and concurrency.
- **Embedding lifecycle:** Store model name and dimensions, version the embedding field, and backfill before switching an index to a new model.
- **Freshness:** Define change-stream or application-write workflows that regenerate embeddings when searchable provider content changes.
- **Pagination:** Use `searchSequenceToken` for lexical deep paging. Preserve identical query and sort semantics between pages. Hybrid and vector experiences usually use bounded top-K retrieval or a larger candidate window instead.
- **Security and PHI:** Keep this synthetic dataset separate from regulated data. Apply least-privilege database roles, network controls, encryption, audit logging, retention rules, and legal/compliance review before using member or patient data.
- **Observability:** Track stage latency, query volume, error rate, no-result queries, index status, embedding failures, rerank failures, and relevance metrics.
- **Resilience:** Decide whether a Voyage outage should fall back to lexical retrieval, skip reranking, or use cached embeddings. Do not silently change ranking behavior.
- **Rollout:** Test relevance changes with shadow traffic or an A/B framework before changing production weights or synonym mappings.

## Competitive Positioning

- Atlas keeps operational provider data, filtering fields, geospatial coordinates, lexical mappings, and vectors in one governed document model.
- Search results return the current provider record without a separate change-data-capture pipeline feeding an external search estate.
- Atlas Search, Vector Search, `$searchMeta`, geo filtering, and `$rankFusion` use one aggregation API and one security boundary.
- The practical comparison is operational simplicity, freshness, and developer workflow, not a claim that every workload has one universal winner.
- Use the live pipeline, index definitions, and execution trace to ground the discussion in observable implementation details.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Search returns an index error | Confirm `search_index` is `READY` and the configured name matches `.env`. |
| Synonym queries fail | Run `make synonyms`, then `make indexes`; confirm the source collection and mapping names match. |
| Vector queries fail | Confirm every vector has 1024 dimensions and `VECTOR_INDEX_NAME` matches the deployed index. |
| `$rankFusion` falls back | Confirm MongoDB 8.0+ and `USE_ATLAS_RANK_FUSION=true`. |
| Autocomplete is empty | Type at least two characters and confirm `autocomplete_text` is populated and indexed. |
| Pagination repeats results | Keep the query, filters, and sort unchanged; verify `provider_id` is indexed as a token tie-breaker. |
| Geo results appear sparse | Increase the candidate window or use a broader radius; vector geo filtering occurs after ANN retrieval in this demo. |
| Rerank is unavailable | Confirm `VOYAGE_API_KEY` and the configured rerank model, then retry without rerank to validate Atlas retrieval independently. |

## Advanced Option: `$scoreFusion`

MongoDB 8.3+ also supports `$scoreFusion`. Use it when score magnitude must influence the final result and each input score can be normalized deliberately. This demo uses `$rankFusion` because lexical, cosine, and rerank values have different scales; rank-based fusion is easier to explain and robust without score normalization. Keep `$scoreFusion` as an advanced design discussion rather than a fourth primary UI mode.

## Talking Points

- Atlas keeps provider search close to operational data instead of synchronizing a separate search estate.
- One document model can serve keyword search, semantic search, filters, autocomplete, and hybrid relevance.
- `$rankFusion` gives a native, single-aggregation hybrid pattern that blends lexical precision with vector recall and exposes explainable rank contributions.
- `$searchMeta` computes result counts and facet buckets from the search index instead of scanning the application result list.
- Search constraints live in `compound.filter`; vector-compatible constraints live in `$vectorSearch.filter`, reducing unnecessary post-processing.
- The vector candidate pool starts at roughly 20 times the requested result window, then can be tuned against measured recall and latency.
- Atlas Search supports relevance tuning where healthcare search needs it: aliases, procedures, symptoms, specialties, network filters, availability, language, and distance.
- Voyage reranking can be added as a final relevance layer without replacing Atlas retrieval.
- Compared with running OpenSearch or Elasticsearch beside MongoDB, this demo reduces data movement, duplicate indexing logic, and consistency gaps.

## Document Shape

The seed script loads 100 fictional provider documents across 65 specialties. The corpus intentionally includes close lexical competitors and broader semantic alternatives so the mode comparison produces meaningful rank differences. Each seeded provider document is shaped like:

```json
{
  "document_type": "care_provider",
  "provider_id": "fc-ortho-001",
  "provider_name": "Northstar Orthopedic Institute",
  "provider_type": "Facility",
  "specialty_name": "Orthopedic Surgery",
  "aliases": ["ortho", "orthopedics", "bone doctor", "sports medicine"],
  "conditions": ["knee pain", "hip pain", "joint pain", "shoulder injury", "arthritis"],
  "procedures": ["knee replacement", "ACL repair", "hip replacement", "rotator cuff repair"],
  "care_summary": "Orthopedic surgeons and sports medicine clinicians treating joint pain...",
  "insurance_networks": ["Humana Choice PPO", "Medicare Advantage"],
  "address_line1": "120 Congress Avenue",
  "phone": "(512) 555-0100",
  "next_available": "Today, 3:20 PM",
  "city": "Austin",
  "state": "TX",
  "distance_miles": 2.4,
  "location": {
    "type": "Point",
    "coordinates": [-97.7431, 30.2711]
  },
  "rating": 4.8,
  "accepting_new_patients": true,
  "telehealth": false,
  "embedding": [0.0123]
}
```

The seed script also adds `autocomplete_text` and three normalized filter helper fields. Every retrieval path requires `document_type = care_provider`, so unrelated embedded documents can safely coexist in the development collection without appearing in FindCare results.

## Index Design

- `search_index` uses an explicit 22-field mapping. Only fields referenced by a Search operator or stable pagination sort are indexed; source-only fields such as ZIP code and review count remain returnable from MongoDB without adding Search index surface area.
- The `medical_synonyms` mapping reads from a dedicated same-database collection. The query uses a synonym-aware text clause separately from fuzzy matching because those options serve different retrieval behaviors.
- `aliases` remain document-level vocabulary for provider-specific names, abbreviations, and member-facing labels. Synonyms remain centrally governed equivalence rules applied across the corpus. The synonym clause does not search `aliases`, preventing the same term from receiving duplicate alias and synonym boosts.
- `specialty_filter`, `networks_filter`, and `languages_filter` are intentional token mappings. They support exact `equals` filters and `$searchMeta` facets while the corresponding human-readable fields remain analyzed for text retrieval.
- `vector_index` contains one 1024-dimension, cosine-similarity vector plus seven fields used by `$vectorSearch.filter`. Scalar quantization reduces vector memory while preserving the demo's retrieval quality.
- `dynamic: false` keeps both index intent and cost visible. Adding a new searchable or filterable field is an explicit schema decision.
- Member decision fields such as address, phone, appointment availability, review count, and ZIP code remain in the same provider document and are returned directly after retrieval without bloating either search index.

## Relevance Design

- Full text combines a high-boost phrase clause, boosted provider/specialty aliases, fuzzy clinical terms, synonym-expanded canonical clinical text, and contextual summary text. Multi-word queries pass through a non-scoring two- or three-concept recall gate; administrative words such as `accepting`, `patients`, and `telehealth` cannot satisfy it. Exact curated synonym phrases bypass the literal gate. This prevents a generic token such as `surgery` from admitting unrelated specialties while preserving typo and conversational-query recall. Fuzzy matching uses one edit with a two-character exact prefix; autocomplete runs through its own endpoint and operator.
- Vector Search uses Voyage `voyage-4`, cosine similarity, scalar quantization, prefilters, and an ANN candidate pool of at least 20 times the requested result count.
- Hybrid Search sends bounded `$search` and `$vectorSearch` input pipelines to native `$rankFusion`. Balanced weighting is 55/45; the demo also exposes lexical-first 75/25 and semantic-first 35/65 profiles.
- Result badges identify the score source rather than presenting unlike values as equivalent: `Search` is the Atlas Search relevance score, `Vector` is the Atlas Vector Search similarity score, `RRF` is the rank-fusion score, and `Rerank` is Voyage's final relevance score.
- Voyage rerank is optional and only reranks the Atlas candidate set. It does not replace retrieval, filtering, geo constraints, or Atlas index management.
- These values are demo defaults, not universal production settings. Validate weights, candidate counts, and field boosts against labeled healthcare queries and target latency before rollout.
- Opening `static/index.html` directly provides a query-aware interface preview only. It intentionally reports no Atlas score or execution timing; use the HTTP application URL for live Search, Vector Search, facets, synonyms, and fusion.

## Geo Patterns

The demo includes a GeoJSON `location` field for each provider and two complementary index patterns:

- Atlas Search `geo` mapping on `location`, used by `geoWithin` filters inside `$search.compound.filter` so lexical filtering stays inside the Search stage.
- A regular MongoDB `2dsphere` index on `location`, used by the live demo for nearby provider/map-style filtering around lexical, vector, and hybrid result sets.

The UI exposes origin, radius, and sort controls. `Sort = Distance` keeps the selected retrieval mode but reorders returned candidates by calculated distance from the selected origin. The `Geo query` modal shows both the Atlas Search `geoWithin` pattern and the regular `2dsphere` index pattern.

## Notes

- Keep `VOYAGE_EMBED_DIMENSIONS` aligned with `indexes/vector_index.json`.
- After changing indexed fields, run `make seed`, then `make indexes`, and wait until both indexes report `READY` before validating relevance.
- `$rankFusion` requires MongoDB 8.0+. `$scoreFusion` requires MongoDB 8.3+ and is not used in this demo.
- `$rankFusion` input pipelines are bounded with explicit limits. Atlas executes those input pipelines and fuses their ranks in one aggregation.
- The sample data is fictional and intended for search demonstration only.
