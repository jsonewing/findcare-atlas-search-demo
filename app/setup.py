from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import re
import shutil
from typing import Any

from dotenv import set_key
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import voyageai

from app.config import ROOT, get_settings, reload_settings
from app.db import close_client
from app.embeddings import close_voyage_client
from app.provisioning import provision_demo_events


ENV_PATH = ROOT / ".env"
NAMESPACE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SetupValidationError(ValueError):
    pass


def _atlas_target(uri: str) -> str:
    if not uri:
        return "Not configured"
    authority = uri.split("@", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    return authority or "Configured Atlas cluster"


def setup_summary() -> dict[str, Any]:
    settings = get_settings()
    atlas_configured = bool(settings.atlas_uri)
    voyage_configured = bool(settings.voyage_api_key)
    return {
        "configured": atlas_configured and voyage_configured,
        "atlas_configured": atlas_configured,
        "voyage_configured": voyage_configured,
        "atlas_target": _atlas_target(settings.atlas_uri),
        "database": settings.atlas_db,
        "collection": settings.atlas_collection,
        "storage": ".env in this FindCare folder",
    }


def _namespace(value: str, label: str) -> str:
    cleaned = value.strip()
    if not NAMESPACE_PATTERN.fullmatch(cleaned):
        raise SetupValidationError(
            f"{label} must contain only letters, numbers, underscores, or hyphens."
        )
    return cleaned


def _redacted_error(exc: Exception, *secrets: str) -> str:
    detail = str(exc)
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "<redacted>")
    return detail


def _validate_atlas(uri: str, database: str, collection_name: str) -> dict[str, Any]:
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise SetupValidationError("Atlas URI must begin with mongodb:// or mongodb+srv://.")
    client = MongoClient(
        uri,
        appname="findcare-portable-setup",
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
    )
    try:
        client.admin.command("ping")
        collection = client[database][collection_name]
        documents = collection.count_documents({"document_type": "care_provider"})
        try:
            indexes = {
                item["name"]: {
                    "status": item.get("status", "UNKNOWN"),
                    "queryable": bool(item.get("queryable", False)),
                }
                for item in collection.list_search_indexes()
            }
        except OperationFailure as exc:
            if exc.code != 26:
                raise
            indexes = {}
        settings = get_settings()
        required = (settings.search_index_name, settings.vector_index_name)
        indexes_ready = all(indexes.get(name, {}).get("queryable") for name in required)
        return {
            "target": _atlas_target(uri),
            "documents": documents,
            "indexes": {name: indexes.get(name, {"status": "MISSING", "queryable": False}) for name in required},
            "ready": documents > 0 and indexes_ready,
        }
    except SetupValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SetupValidationError(
            f"Atlas connection failed: {_redacted_error(exc, uri)}"
        ) from exc
    finally:
        client.close()


def _validate_voyage(api_key: str) -> None:
    if len(api_key) < 12:
        raise SetupValidationError("Voyage API key appears incomplete.")
    settings = get_settings()
    try:
        voyageai.Client(api_key=api_key).embed(
            ["FindCare portable setup validation"],
            model=settings.voyage_embed_model,
            input_type="query",
            output_dimension=settings.voyage_embed_dimensions,
        )
    except Exception as exc:  # noqa: BLE001
        raise SetupValidationError(
            f"Voyage API validation failed: {_redacted_error(exc, api_key)}"
        ) from exc


def _persist_env(values: dict[str, str], env_path: Path = ENV_PATH) -> None:
    pending = env_path.with_name(f"{env_path.name}.pending")
    if env_path.exists():
        shutil.copyfile(env_path, pending)
    else:
        pending.write_text("", encoding="utf-8")
    try:
        for key, value in values.items():
            set_key(str(pending), key, value, quote_mode="always")
        os.chmod(pending, 0o600)
        os.replace(pending, env_path)
    finally:
        pending.unlink(missing_ok=True)


def configure_local_events(
    atlas_uri: str,
    voyage_api_key: str,
    database: str,
    collection: str,
    install_demo_data: bool = True,
) -> Iterator[dict[str, Any]]:
    current = get_settings()
    resolved_uri = atlas_uri.strip() or current.atlas_uri
    resolved_key = voyage_api_key.strip() or current.voyage_api_key
    current_stage = "input"
    try:
        if not resolved_uri or not resolved_key:
            raise SetupValidationError("Atlas URI and Voyage API key are required.")
        resolved_database = _namespace(database, "Database")
        resolved_collection = _namespace(collection, "Collection")

        current_stage = "atlas"
        yield {"stage": current_stage, "status": "running", "message": "Connecting to MongoDB Atlas"}
        readiness = _validate_atlas(resolved_uri, resolved_database, resolved_collection)
        yield {
            "stage": current_stage,
            "status": "complete",
            "message": f"Atlas connected; {readiness['documents']} provider documents found",
            "readiness": readiness,
        }

        current_stage = "voyage"
        yield {"stage": current_stage, "status": "running", "message": "Validating Voyage AI credentials"}
        _validate_voyage(resolved_key)
        yield {"stage": current_stage, "status": "complete", "message": "Voyage AI connection verified"}

        current_stage = "data"
        if readiness["ready"]:
            yield {
                "stage": current_stage,
                "status": "complete",
                "message": f"Existing demo is ready with {readiness['documents']} providers",
                "readiness": readiness,
            }
        elif install_demo_data:
            yield {
                "stage": current_stage,
                "status": "running",
                "message": "Preparing the bundled FindCare provider corpus",
            }
            try:
                for progress in provision_demo_events(
                    resolved_uri,
                    resolved_key,
                    resolved_database,
                    resolved_collection,
                    current,
                ):
                    yield {"stage": current_stage, "status": "running", **progress}
            except Exception as exc:  # noqa: BLE001
                raise SetupValidationError(
                    f"Demo preparation failed: {_redacted_error(exc, resolved_uri, resolved_key)}"
                ) from exc
            readiness = _validate_atlas(resolved_uri, resolved_database, resolved_collection)
            if not readiness["ready"]:
                raise SetupValidationError(
                    "Provider data was loaded, but Atlas Search indexes are not queryable yet. "
                    "Wait a few minutes and run setup again."
                )
            yield {
                "stage": current_stage,
                "status": "complete",
                "message": f"Bundled demo ready with {readiness['documents']} providers",
                "readiness": readiness,
            }
        else:
            yield {
                "stage": current_stage,
                "status": "warning",
                "message": "Connected, but provider data or search indexes are missing",
                "readiness": readiness,
            }

        current_stage = "save"
        yield {"stage": current_stage, "status": "running", "message": "Saving local credentials securely"}
        values = {
            "ATLAS_URI": resolved_uri,
            "ATLAS_DB": resolved_database,
            "ATLAS_COLLECTION": resolved_collection,
            "VOYAGE_API_KEY": resolved_key,
        }
        _persist_env(values)
        close_client()
        close_voyage_client()
        reload_settings(values)
        yield {"stage": current_stage, "status": "complete", "message": "Saved to a private local .env file"}

        summary = setup_summary()
        summary["readiness"] = readiness
        summary["message"] = (
            "Connections verified. FindCare is ready."
            if readiness["ready"]
            else "Connections verified. Provider data or search indexes still need preparation."
        )
        yield {"stage": "ready", "status": "complete", "setup": summary, "message": summary["message"]}
    except SetupValidationError as exc:
        yield {"stage": current_stage, "status": "error", "message": str(exc)}
