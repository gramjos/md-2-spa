"""
Front matter extraction for Obsidian Vault → HTML conversion.

Parses YAML front matter (between --- delimiters) from .md files and
enriches manifest nodes with a ``metadata`` field.

Supported value types:
  - datetime   2026-02-07T14:04:00  → ISO string
  - date       2026-02-13           → ISO string
  - number     987                  → int / float
  - list       [a, b, c]            → list
  - bool       true / false         → bool  (checkbox)
  - text       any string           → str

A ``title`` key in front matter overrides the filename-derived title.
"""

import re
from datetime import date, datetime
from pathlib import Path

import yaml

from manifest import slugify


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?", re.DOTALL)


def extract_frontmatter(text: str) -> tuple[dict, str]:
    """Split leading YAML front matter from markdown body.

    Returns:
        (metadata_dict, body_without_frontmatter)
        If no front matter is found, returns ({}, original_text).
    """
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        return {}, text

    raw_yaml = m.group(1)
    body = text[m.end():]

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        # Malformed YAML → treat as no front matter
        return {}, text

    if not isinstance(parsed, dict):
        return {}, text

    metadata = _normalise_values(parsed)
    return metadata, body


def _normalise_values(data: dict) -> dict:
    """Convert date/datetime objects to ISO strings for JSON serialisation."""
    out: dict = {}
    for key, value in data.items():
        out[key] = _normalise(value)
    return out


def _normalise(value):
    """Recursively normalise a single value."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, dict):
        return _normalise_values(value)
    # int, float, bool, str, None — all JSON-native
    return value


# ---------------------------------------------------------------------------
# Manifest enrichment
# ---------------------------------------------------------------------------

def enrich_manifest(manifest: dict, vault_path: Path) -> dict:
    """Populate ``metadata`` on every file/directory node in-place.

    For each eligible node the corresponding .md source is read,
    front matter is extracted, and the result is stored as
    ``node["metadata"]``.  If the front matter contains a ``title``
    key its value overrides the node title.

    Args:
        manifest:   The manifest dict produced by ``generate_manifest()``.
        vault_path: Resolved path to the source vault directory.

    Returns:
        The same manifest dict (mutated in-place) for convenience.
    """
    items = manifest["items"]

    for node in items.values():
        ntype = node["type"]
        if ntype not in ("file", "directory"):
            continue

        src_file = _resolve_source(node, vault_path, slugify)
        if src_file is None or not src_file.is_file():
            continue

        content = src_file.read_text(encoding="utf-8")
        metadata, _ = extract_frontmatter(content)

        if not metadata:
            continue

        # title override
        if "title" in metadata:
            node["title"] = str(metadata.pop("title"))

        if metadata:
            node["metadata"] = metadata

    count = sum(1 for n in items.values() if "metadata" in n)
    print(f"  [frontmatter] Enriched {count} node(s) with metadata.")

    return manifest


# ---------------------------------------------------------------------------
# Source resolution helpers
# ---------------------------------------------------------------------------

def _resolve_source(node: dict, vault_path: Path, slugify) -> Path | None:
    """Find the .md source for a manifest node."""
    slug = node["slug"]
    ntype = node["type"]

    if ntype == "directory":
        return _find_readme_for_slug(slug, vault_path, slugify)
    else:
        return _find_file_for_slug(slug, vault_path, slugify)


def _find_file_for_slug(slug: str, vault_path: Path, slugify) -> Path | None:
    """Locate the .md source file for a file-type slug."""
    # Fast path: literal path
    candidate = vault_path / (slug + ".md")
    if candidate.is_file():
        return candidate

    # Slug segments may be kebab-cased — walk the real dirs
    parts = slug.split("/")
    if parts[0] == "root":
        parts = parts[1:]

    filename_slug = parts[-1]
    parent_parts = parts[:-1]

    parent = vault_path
    for p in parent_parts:
        parent = _match_dir(parent, p, slugify)
        if parent is None:
            return None

    # Scan files in parent directory
    if not parent.is_dir():
        return None

    for entry in parent.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".md":
            if entry.name.lower() == "readme.md":
                continue
            if slugify(entry.stem) == filename_slug:
                return entry

    return None


def _find_readme_for_slug(slug: str, vault_path: Path, slugify) -> Path | None:
    """Locate the README.md for a directory-type slug."""
    if slug == "root":
        target = vault_path
    else:
        parts = slug.split("/")
        target = vault_path
        for p in parts:
            target = _match_dir(target, p, slugify)
            if target is None:
                return None

    if target is None or not target.is_dir():
        return None

    for entry in target.iterdir():
        if entry.is_file() and entry.name.lower() == "readme.md":
            return entry
    return None


def _match_dir(parent: Path, slug_segment: str, slugify) -> Path | None:
    """Match a slug segment to an actual subdirectory."""
    # Fast path
    candidate = parent / slug_segment
    if candidate.is_dir():
        return candidate

    if not parent.is_dir():
        return None

    for entry in parent.iterdir():
        if entry.is_dir() and slugify(entry.name) == slug_segment:
            return entry
    return None
