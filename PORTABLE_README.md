# FindCare Search Portable Demo

This package runs the complete FindCare Atlas Search demo locally. It includes 100 synthetic provider records, downloads its own pinned Python runtime, keeps every runtime file inside this folder, and connects to MongoDB Atlas and Voyage AI only after browser-based setup.

> **Synthetic demo notice:** All provider records and network participation are fictional. Third-party trademarks belong to their respective owners; no affiliation or endorsement is implied. This project demonstrates search technology and does not provide medical advice.

## Requirements

- macOS or Linux on Apple Silicon/ARM64 or x86-64
- `curl`, `tar`, `shasum` or `sha256sum`, and internet access for first launch
- Ongoing network access to MongoDB Atlas, Voyage AI, and OpenStreetMap tiles
- A MongoDB 8.0+ Atlas cluster; setup can prepare an empty namespace using the packaged provider corpus and index definitions
- An Atlas database user that can read and write the selected namespace and create Search, Vector Search, and regular indexes
- A Voyage AI API key
- The computer's current outbound IP in the Atlas project Network Access list, unless Atlas PrivateLink or peering is used

## First Launch

On macOS, double-click `start.command`. If macOS blocks it, right-click the file and select **Open**.

On macOS or Linux from a terminal:

```bash
./run.sh
```

The launcher displays five setup stages while it downloads and SHA-256 verifies pinned Python 3.12.13, creates `.venv`, installs pinned dependencies, verifies port ownership, and starts FindCare at `http://127.0.0.1:8035`. The browser opens only after the local readiness endpoint succeeds.

The first browser session asks for the Atlas URI and Voyage API key. Leave **Prepare this namespace when needed** selected to install missing assets from the package: 100 fictional providers, 12 medical synonym mappings, `search_index`, `vector_index`, and `location_2dsphere`. Provider embeddings are generated with the supplied Voyage key only when packaged provider records are missing. Existing ready demo collections are detected and left unchanged.

**Verify and save** streams Atlas, Voyage, provider-data, index-build, local-save, and portal-readiness status. Search indexes can take several minutes to become queryable. Credentials are saved only in `.env` with owner-only permissions and are never returned to the browser.

## Restart And Port Selection

Press `Ctrl+C` in the launcher terminal to stop FindCare. Run `./run.sh` again to restart it. The launcher restarts only a prior FindCare process owned by this extracted folder and refuses to terminate an unrelated listener.

Use a different local port when needed:

```bash
PORT=8040 ./run.sh
```

For automated or headless use:

```bash
NO_BROWSER=1 ./run.sh
```

The server always binds to `127.0.0.1`; `PORT` does not make it remotely accessible.

## Configuration

Use the **Connected** button in the header to verify a different Atlas URI, Voyage key, database, or collection. Blank credential fields retain existing saved values. Delete `.env` to return to first-run state.

Browser setup prepares a new or incomplete demo namespace only when its preparation option is selected. It adds missing packaged provider IDs, upserts the demo's named synonym mappings, and creates missing indexes; it does not delete unrelated records. The same operations remain available as development commands:

```bash
make seed
make indexes
make smoke
```

These commands require configured credentials and may call Voyage or modify the selected Atlas namespace. The complete demo flow and technical notes are in `DEMO_GUIDE.md`.

## Rebuild And Test

```bash
make test
make dist
make verify-dist
```

`make dist` creates a versioned ZIP and matching SHA-256 file under `dist/`. `make verify-dist` performs a clean extraction, first-run installation, API/UI readiness check, secret-free state check, warm restart, and unrelated-port safety test.

## Verify The Download

From the directory containing both release files:

```bash
shasum -a 256 -c findcare-search-portable-v1.2.3.zip.sha256
```

On Linux, `sha256sum -c` can be used instead.

## Local Files And External Services

`vendor/`, `.venv/`, `.runtime/`, and `.env` remain inside this extracted folder. They are excluded from rebuilt distributions. The ZIP includes the synthetic provider fixture without generated embeddings or credentials. Atlas stores the installed corpus, synonyms, and indexes; Voyage AI supplies document/query embeddings and optional reranking. OpenStreetMap supplies browser map tiles.
