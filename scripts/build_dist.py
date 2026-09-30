from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

from app.sample_data import prepared_sample_documents


ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = ROOT / "dist"
VERSION_FILE = ROOT / "VERSION"
PACKAGE_PREFIX = "findcare-search-portable"
SCRIPT_FILES = (
    "build_dist.py",
    "create_indexes.py",
    "evaluate_search.py",
    "seed_findcare.py",
    "seed_synonyms.py",
    "setup-python.sh",
    "smoke_search.py",
    "verify_dist.py",
)


def copy_tree(source: str, package_dir: Path) -> None:
    shutil.copytree(
        ROOT / source,
        package_dir / source,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".DS_Store",
            ".pytest_cache",
            "pdf_ingest.py",
        ),
    )


def validate_version(version: str) -> None:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"VERSION must use MAJOR.MINOR.PATCH; found {version!r}")


def validate_archive(archive: Path, package_name: str) -> None:
    forbidden_parts = {
        ".env",
        ".env.pending",
        ".venv",
        ".runtime",
        ".pytest_cache",
        "__pycache__",
        "dist",
        "generated",
        "uploads",
        "vendor",
    }
    with zipfile.ZipFile(archive) as package_zip:
        bad_member = package_zip.testzip()
        if bad_member:
            raise RuntimeError(f"ZIP verification failed at {bad_member}")
        names = package_zip.namelist()
        if not names or not all(name.startswith(f"{package_name}/") for name in names):
            raise RuntimeError("ZIP does not contain exactly one versioned package root")
        for name in names:
            path = Path(name)
            if forbidden_parts.intersection(path.parts):
                raise RuntimeError(f"Forbidden runtime or secret path included: {name}")
            if path.suffix.lower() in {".pdf", ".zip"}:
                raise RuntimeError(f"Generated or uploaded artifact included: {name}")
            if path.name == "pdf_ingest.py":
                raise RuntimeError(f"Unrelated PDF ingestion module included: {name}")
        required = {
            f"{package_name}/run.sh",
            f"{package_name}/start.command",
            f"{package_name}/README.md",
            f"{package_name}/VERSION",
            f"{package_name}/app/main.py",
            f"{package_name}/static/index.html",
            f"{package_name}/indexes/search_index.json",
            f"{package_name}/indexes/vector_index.json",
            f"{package_name}/data/findcare_providers.json",
        }
        missing = required.difference(names)
        if missing:
            raise RuntimeError(f"ZIP is missing required files: {sorted(missing)}")
        providers = json.loads(
            package_zip.read(f"{package_name}/data/findcare_providers.json")
        )
        if len(providers) != 100:
            raise RuntimeError(f"Expected 100 bundled providers; found {len(providers)}")
        if any("embedding" in provider for provider in providers):
            raise RuntimeError("Provider fixture must not contain generated embeddings")

        env_path = ROOT / ".env"
        if env_path.exists():
            secret_values = []
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() in {"ATLAS_URI", "VOYAGE_API_KEY"}:
                    secret = value.strip().strip("'\"")
                    if secret:
                        secret_values.append(secret.encode())
            for name in names:
                if name.endswith("/"):
                    continue
                contents = package_zip.read(name)
                if any(secret in contents for secret in secret_values):
                    raise RuntimeError(f"A configured credential was found in {name}")


def build() -> tuple[Path, Path]:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    validate_version(version)
    package_name = f"{PACKAGE_PREFIX}-v{version}"
    archive = DIST_ROOT / f"{package_name}.zip"
    checksum = DIST_ROOT / f"{archive.name}.sha256"
    DIST_ROOT.mkdir(exist_ok=True)

    for stale in DIST_ROOT.glob(f"{PACKAGE_PREFIX}*"):
        if stale.is_dir():
            shutil.rmtree(stale)
        else:
            stale.unlink()

    with tempfile.TemporaryDirectory(prefix="findcare-release-") as staging:
        package_dir = Path(staging) / package_name
        package_dir.mkdir()

        for directory in ("app", "indexes", "static", "tests"):
            copy_tree(directory, package_dir)

        data_dir = package_dir / "data"
        data_dir.mkdir()
        (data_dir / "findcare_providers.json").write_text(
            json.dumps(prepared_sample_documents(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        scripts_dir = package_dir / "scripts"
        scripts_dir.mkdir()
        for name in SCRIPT_FILES:
            shutil.copy2(ROOT / "scripts" / name, scripts_dir / name)

        for name in (
            ".env.example",
            ".gitignore",
            "Makefile",
            "VERSION",
            "requirements.txt",
            "run.sh",
            "start.command",
            "start.sh",
        ):
            shutil.copy2(ROOT / name, package_dir / name)
        shutil.copy2(ROOT / "PORTABLE_README.md", package_dir / "README.md")
        shutil.copy2(ROOT / "README.md", package_dir / "DEMO_GUIDE.md")

        for relative in (
            "run.sh",
            "start.command",
            "start.sh",
            "scripts/setup-python.sh",
        ):
            path = package_dir / relative
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        shutil.make_archive(str(archive.with_suffix("")), "zip", staging, package_name)

    validate_archive(archive, package_name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, checksum


if __name__ == "__main__":
    output, digest_file = build()
    print(f"Built {output}")
    print(f"Checksum: {digest_file.read_text(encoding='ascii').strip()}")
