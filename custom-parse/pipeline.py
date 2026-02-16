"""
Content processing for the Obsidian parser.

Orchestrates the build process:
- Copies graphics
- Parses file pages
- Parses directory READMEs
- Manages file system lookups
"""

import shutil
from pathlib import Path
import mistune
from frontmatter import extract_frontmatter
import renderer
from manifest import slugify

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_source_md(vault_path: Path, slug: str) -> Path | None:
    """Find the source .md file for a slug, handling name mismatches.

    The slug is kebab-cased but the original filename might have spaces,
    underscores, or mixed case.
    """
    parts = slug.split("/")
    filename_slug = parts[-1]
    parent_parts = parts[:-1]

    parent_dir = vault_path
    for p in parent_parts:
        found = None
        if parent_dir.is_dir():
            for entry in parent_dir.iterdir():
                if entry.is_dir():
                    if slugify(entry.name) == p:
                        found = entry
                        break
        if found:
            parent_dir = found
        else:
            return None

    if not parent_dir.is_dir():
        return None

    for entry in parent_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".md":
            if entry.name.lower() == "readme.md":
                continue
            if slugify(entry.stem) == filename_slug:
                return entry

    return None


def _resolve_slug_to_dir(vault_path: Path, slug: str) -> Path | None:
    """Resolve a slugified path back to the real filesystem directory.

    Walks each segment of the slug, matching against actual directory names
    via slugify() to handle spaces, mixed case, etc.
    e.g. slug='moss/moss-1/graphics' → vault_path/'moss'/'moss 1'/'graphics'
    """
    current = vault_path
    for part in slug.split("/"):
        # Try the literal name first (fast path)
        candidate = current / part
        if candidate.is_dir():
            current = candidate
            continue
        # Fallback: scan siblings and match by slug
        found = None
        if current.is_dir():
            for entry in current.iterdir():
                if entry.is_dir() and slugify(entry.name) == part:
                    found = entry
                    break
        if found:
            current = found
        else:
            return None
    return current


def _find_readme(directory: Path) -> Path | None:
    """Find README.md (case-insensitive) in a directory."""
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() == "readme.md":
            return entry
    return None


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def copy_graphics(manifest: dict, vault_path: Path, output_path: Path) -> None:
    """Copy graphics assets from vault to output directory."""
    for node in manifest["items"].values():
        if node["type"] != "graphics":
            continue

        slug = node["slug"]
        src_dir = _resolve_slug_to_dir(vault_path, slug)
        dst_dir = output_path / slug

        if src_dir is None or not src_dir.is_dir():
            print(f"  [warn] Graphics dir not found: {vault_path / slug}")
            continue

        dst_dir.mkdir(parents=True, exist_ok=True)

        for asset in node.get("assets", []):
            src_file = src_dir / asset
            dst_file = dst_dir / asset
            if src_file.is_file():
                shutil.copy2(src_file, dst_file)

    print("  [graphics] Assets copied.")


def parse_file_pages(manifest: dict, vault_path: Path, output_path: Path, md: mistune.Markdown) -> None:
    """Parse each file-type node's .md → .html fragment."""
    items = manifest["items"]

    for node in items.values():
        if node["type"] != "file":
            continue

        slug = node["slug"]
        src_file = vault_path / (slug + ".md")

        if not src_file.is_file():
            src_file = _find_source_md(vault_path, slug)
            if src_file is None:
                print(f"  [warn] Source not found for: {slug}")
                continue

        content = src_file.read_text(encoding="utf-8")
        _, content = extract_frontmatter(content)
        html = md(content)

        out_file = output_path / node["content_path"].lstrip("/")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html, encoding="utf-8")

    print("  [files] Content pages parsed.")


def parse_readme_pages(manifest: dict, vault_path: Path, output_path: Path, md: mistune.Markdown) -> None:
    """Parse each directory-type node's README.md → HTML fragment with auto-nav."""
    items = manifest["items"]

    for node in items.values():
        if node["type"] != "directory":
            continue

        slug = node["slug"]
        is_root = slug == "root"

        if is_root:
            src_dir = vault_path
        else:
            src_dir = _resolve_slug_to_dir(vault_path, slug)
            if src_dir is None:
                print(f"  [warn] Directory not found for slug: {slug}")
                continue

        readme_file = _find_readme(src_dir)
        if readme_file is None:
            print(f"  [warn] README not found in: {src_dir}")
            continue

        content = readme_file.read_text(encoding="utf-8")
        _, content = extract_frontmatter(content)
        html = md(content)

        out_file = output_path / node["content_path"].lstrip("/")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html, encoding="utf-8")

    print("  [readme] Home pages parsed.")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_vault(manifest: dict, vault_path: Path, output_path: Path) -> None:
    """Convert markdown files to HTML based on the manifest.

    Args:
        manifest:    The manifest dict (as produced by manifest.generate_manifest).
        vault_path:  Resolved path to the source Obsidian vault.
        output_path: Resolved path to the output directory.
    """
    md = renderer.create_parser(manifest)

    # Job 1: Copy graphics
    copy_graphics(manifest, vault_path, output_path)

    # Job 2: Parse file content pages
    parse_file_pages(manifest, vault_path, output_path, md)

    # Job 3: Parse README home pages with auto-nav
    parse_readme_pages(manifest, vault_path, output_path, md)
