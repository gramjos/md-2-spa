"""
Manifest Generator for Obsidian Vault → HTML conversion.

Walks an Obsidian vault directory and produces a manifest JSON file (m.json)
that serves as the source of truth for the parser/converter.

Rules:
  1. README signal — only directories containing a README.md (case-insensitive)
     are eligible for conversion.
  2. Graphics exception — directories named exactly "graphics" are exempt from
     needing a README. They hold media assets.
  3. Hidden/system directories (.obsidian, .excalidraw) and .DS_Store are ignored.

Usage:
    python manifest.py /path/to/vault
    python manifest.py /path/to/vault -o manifest.json
    python manifest.py /path/to/vault --title "My Site"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IGNORE_DIRS = {".obsidian", ".excalidraw"}
IGNORE_FILES = {".DS_Store"}
GRAPHICS_DIR_NAME = "graphics"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert a string to a URL-friendly kebab-case slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s\-_/]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def make_id(slug: str, node_type: str) -> str:
    """Create a manifest node ID from a slug and type.
    
    Uses the full slug path to ensure uniqueness across directories.
    'root/graphics'       → 'root-graphics'
    'moss/graphics'       → 'moss-graphics'
    'math/guess'          → 'math-guess-file'  (but simplified when unambiguous)
    """
    suffix = "-dir" if node_type == "directory" else (
        "-graphics" if node_type == "graphics" else "-file"
    )
    # For graphics, use parent + "graphics" to disambiguate
    # For files, use last segment only
    parts = slug.strip("/").split("/")
    if node_type == "graphics":
        # e.g. "moss/graphics" → "moss-graphics", "graphics" → "root-graphics"
        if len(parts) >= 2:
            base = parts[-2]
        else:
            base = "root"
        return f"{base}{suffix}"
    else:
        base = parts[-1] if parts[-1] else parts[0]
        return f"{base}{suffix}"


def make_title(name: str) -> str:
    """Derive a display title from a filename or directory name.
    
    'golden_file' → 'Golden File'
    'moss 1'      → 'Moss 1'
    """
    name = name.replace("_", " ").replace("-", " ")
    return name.title()


def has_readme(directory: Path) -> str | None:
    """Check if a directory contains a README.md (case-insensitive).
    
    Returns the actual filename if found, None otherwise.
    """
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() == "readme.md":
            return entry.name
    return None


def is_graphics_dir(path: Path) -> bool:
    """Check if a directory is a graphics directory."""
    return path.name.lower() == GRAPHICS_DIR_NAME


def should_ignore(path: Path) -> bool:
    """Check if a file or directory should be ignored."""
    if path.name in IGNORE_FILES:
        return True
    if path.is_dir() and path.name in IGNORE_DIRS:
        return True
    return False


def collect_assets(graphics_path: Path) -> list[str]:
    """Collect media asset filenames from a graphics directory."""
    assets = []
    for entry in sorted(graphics_path.iterdir()):
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
            assets.append(entry.name)
    return assets


# ---------------------------------------------------------------------------
# Core: recursive directory walker
# ---------------------------------------------------------------------------

def walk_directory(dir_path: Path, vault_root: Path, root_title: str | None = None) -> dict | None:
    """Recursively walk a directory and build manifest nodes.
    
    Returns a dict with:
        - "node": the manifest node for this directory
        - "extra_nodes": flat list of all descendant nodes (including this one)
    Or None if the directory is not eligible (no README).
    """
    # Check README signal
    readme_name = has_readme(dir_path)
    if readme_name is None:
        return None

    is_root = (dir_path == vault_root)
    rel_path = dir_path.relative_to(vault_root)
    dir_slug = "root" if is_root else slugify(str(rel_path))

    # Build the directory node
    dir_id = "root-dir" if is_root else make_id(dir_slug, "directory")
    title = root_title if (is_root and root_title) else (
        "Root" if is_root else make_title(dir_path.name)
    )

    # content_path for the directory is its README.html
    if is_root:
        content_path = "/readme.html"
    else:
        content_path = f"/{dir_slug}/README.html"

    dir_node = {
        "id": dir_id,
        "type": "directory",
        "title": title,
        "slug": dir_slug,
        "content_path": content_path,
        "children": [],
    }

    all_nodes = {}  # id → node
    children_ids = []

    # Iterate over sorted directory entries
    entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))

    for entry in entries:
        if should_ignore(entry):
            continue

        # --- Graphics directory ---
        if entry.is_dir() and is_graphics_dir(entry):
            assets = collect_assets(entry)
            if not assets:
                continue
            g_slug = f"{dir_slug}/graphics" if not is_root else "graphics"
            g_id = make_id(g_slug, "graphics")
            graphics_node = {
                "id": g_id,
                "type": "graphics",
                "slug": g_slug,
                "content_path": f"/{g_slug}/",
                "assets": assets,
            }
            all_nodes[g_id] = graphics_node
            children_ids.append(g_id)
            continue

        # --- Subdirectory (non-graphics) ---
        if entry.is_dir():
            result = walk_directory(entry, vault_root, root_title=None)
            if result is not None:
                sub_node = result["node"]
                children_ids.append(sub_node["id"])
                all_nodes.update(result["all_nodes"])
            continue

        # --- File ---
        if entry.is_file() and entry.suffix.lower() == ".md":
            # Skip the README itself (it's represented by the directory node)
            if entry.name.lower() == "readme.md":
                continue

            file_stem = entry.stem
            file_slug = f"{dir_slug}/{slugify(file_stem)}" if not is_root else slugify(file_stem)
            file_id = make_id(file_slug, "file")

            # Ensure unique ID if collision
            if file_id in all_nodes:
                file_id = slugify(file_slug) + "-file"

            file_node = {
                "id": file_id,
                "type": "file",
                "title": make_title(file_stem),
                "slug": file_slug,
                "content_path": f"/{file_slug}.html",
            }
            all_nodes[file_id] = file_node
            children_ids.append(file_id)

    dir_node["children"] = children_ids
    all_nodes[dir_id] = dir_node

    return {
        "node": dir_node,
        "all_nodes": all_nodes,
    }


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def generate_manifest(vault_path: str, title: str = "Digi Garden") -> dict:
    """Generate the full manifest dictionary from a vault path."""
    vault_root = Path(vault_path).resolve()

    if not vault_root.is_dir():
        print(f"Error: '{vault_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    result = walk_directory(vault_root, vault_root, root_title=title)

    if result is None:
        print(f"Error: No README.md found in root '{vault_path}'.", file=sys.stderr)
        sys.exit(1)

    manifest = {
        "rootId": result["node"]["id"],
        "items": result["all_nodes"],
    }

    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a manifest JSON from an Obsidian vault."
    )
    parser.add_argument(
        "vault_path",
        help="Path to the root of the Obsidian vault.",
    )
    parser.add_argument(
        "-o", "--output",
        default="m.json",
        help="Output file path for the manifest (default: m.json).",
    )
    parser.add_argument(
        "--title",
        default="Digi Garden",
        help="Title for the root directory node (default: 'Digi Garden').",
    )

    args = parser.parse_args()
    manifest = generate_manifest(args.vault_path, title=args.title)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Manifest written to {output_path} ({len(manifest['items'])} nodes)")


if __name__ == "__main__":
    main()
