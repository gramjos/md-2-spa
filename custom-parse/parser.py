"""
Parser for Obsidian Vault → HTML conversion.

Reads the manifest and source .md files, converts markdown to HTML fragments
using mistune with custom plugins for Obsidian syntax, and writes the output.

Supports:
  - Headings, paragraphs, bold, italic, inline code (mistune built-in)
  - ![[image.png]]  → <img> resolved via manifest graphics nodes
  - [[page]]        → <a> resolved via manifest lookup
  - [[page|text]]   → <a> with custom display text
  - ![alt](url)     → <img> (mistune built-in)
  - [text](url)     → <a>   (mistune built-in)
  - Horizontal rules (---)
"""

import re
import shutil
from pathlib import Path

import mistune


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def build_title_index(manifest: dict) -> dict[str, list[dict]]:
    """Build a lookup from lowercase title → list of matching nodes.

    Used for resolving [[wiki-links]] by title.
    """
    index: dict[str, list[dict]] = {}
    for node in manifest["items"].values():
        if node["type"] == "graphics":
            continue
        key = node.get("title", "").lower()
        index.setdefault(key, []).append(node)
    return index


def build_slug_index(manifest: dict) -> dict[str, dict]:
    """Build a lookup from slug → node.

    Used for resolving [[path/page]] style links.
    """
    return {
        node["slug"]: node
        for node in manifest["items"].values()
        if node["type"] != "graphics"
    }


def build_asset_index(manifest: dict) -> dict[str, str]:
    """Build a lookup from asset filename → graphics content_path prefix.

    Used for resolving ![[image.png]] embeds.
    e.g. {"hap.png": "/moss/graphics/", "ani3.gif": "/graphics/"}
    """
    index: dict[str, str] = {}
    for node in manifest["items"].values():
        if node["type"] == "graphics":
            for asset in node.get("assets", []):
                # If duplicate filenames across graphics dirs, last wins.
                # Could be smarter (nearest ancestor), but simple for now.
                index[asset] = node["content_path"]  # e.g. "/graphics/"
    return index


def resolve_wiki_link(target: str, title_index: dict, slug_index: dict) -> tuple[str, str]:
    """Resolve a wiki-link target to (href, display_text).

    Tries:
      1. Exact slug match (for path-style links like "nature/tundra/arctic")
      2. Title match (case-insensitive, e.g. "Arctic")
      3. Slugified target as slug match
      4. Fallback: broken link
    """
    # Handle pipe syntax: [[target|display]]
    if "|" in target:
        target_part, display = target.split("|", 1)
    else:
        target_part = target
        display = None

    target_clean = target_part.strip()
    target_lower = target_clean.lower()

    # 1. Exact slug match
    # Convert forward-slash path to slug format (e.g. "moss/look" already works)
    slug_key = target_clean.replace(" ", "-").lower()
    if slug_key in slug_index:
        node = slug_index[slug_key]
        href = node["content_path"]
        return href, display or node["title"]

    # 2. Title match
    if target_lower in title_index:
        matches = title_index[target_lower]
        if len(matches) == 1:
            node = matches[0]
            href = node["content_path"]
            return href, display or node["title"]
        # Multiple matches — can't resolve without full path
        # Fall through to broken link

    # 3. Try slugified version
    from manifest import slugify
    slugified = slugify(target_clean)
    if slugified in slug_index:
        node = slug_index[slugified]
        href = node["content_path"]
        return href, display or node["title"]

    # 4. Fallback: broken link
    return "#", display or target_clean


def resolve_image_embed(filename: str, asset_index: dict) -> str:
    """Resolve an image embed filename to an absolute content path.

    Returns paths with a leading slash so they are unambiguous
    regardless of which page references them.  The SPA router
    rewrites absolute paths by prepending /content-store.

    e.g. "hap.png" → "/moss/graphics/hap.png"
         "img.png" → "/graphics/img.png"
    """
    filename = filename.strip()
    if filename in asset_index:
        return asset_index[filename] + filename
    # Fallback: assume root graphics
    return f"/graphics/{filename}"


# ---------------------------------------------------------------------------
# Mistune plugins for Obsidian syntax
# ---------------------------------------------------------------------------

def plugin_wiki_embed(md: mistune.Markdown) -> None:
    """Plugin for ![[image.png]] Obsidian image embeds.

    Must be registered BEFORE wiki_link plugin since ![[...]] should
    match before [[...]].

    Uses a named capture group because mistune v3 combines all inline
    patterns into one regex, making positional groups unreliable.
    """
    WIKI_EMBED_PATTERN = r"!\[\[(?P<wiki_embed_target>[^\]]+)\]\]"

    def parse_wiki_embed(inline, m, state):
        filename = m.group("wiki_embed_target")
        state.append_token({"type": "wiki_embed", "raw": filename})
        return m.end()

    md.inline.register("wiki_embed", WIKI_EMBED_PATTERN, parse_wiki_embed, before="link")

    def render_wiki_embed(text):
        filename = text
        src = resolve_image_embed(filename, md.renderer._asset_index)
        alt = filename.rsplit(".", 1)[0] if "." in filename else filename
        return f'<img src="{src}" alt="{alt}" />'

    md.renderer.wiki_embed = render_wiki_embed


def plugin_wiki_link(md: mistune.Markdown) -> None:
    """Plugin for [[page]] and [[page|display]] Obsidian wiki-links."""
    WIKI_LINK_PATTERN = r"\[\[(?P<wiki_link_target>[^\]]+)\]\]"

    def parse_wiki_link(inline, m, state):
        raw = m.group("wiki_link_target")
        state.append_token({"type": "wiki_link", "raw": raw})
        return m.end()

    md.inline.register("wiki_link", WIKI_LINK_PATTERN, parse_wiki_link, before="link")

    def render_wiki_link(text):
        raw = text
        href, display = resolve_wiki_link(
            raw, md.renderer._title_index, md.renderer._slug_index
        )
        return f'<a href="{href}">{display}</a>'

    md.renderer.wiki_link = render_wiki_link


# ---------------------------------------------------------------------------
# Parser factory
# ---------------------------------------------------------------------------

def create_parser(manifest: dict) -> mistune.Markdown:
    """Create a configured mistune Markdown parser with Obsidian plugins.

    The manifest indexes are attached to the renderer so plugins can
    resolve links and images at render time.
    """
    md = mistune.create_markdown(
        escape=False,
        plugins=[plugin_wiki_embed, plugin_wiki_link],
    )

    # Attach manifest indexes to the renderer for link/image resolution
    title_index = build_title_index(manifest)
    slug_index = build_slug_index(manifest)
    asset_index = build_asset_index(manifest)

    md.renderer._title_index = title_index
    md.renderer._slug_index = slug_index
    md.renderer._asset_index = asset_index

    return md


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def copy_graphics(manifest: dict, vault_path: Path, output_path: Path) -> None:
    """Copy graphics assets from vault to output directory."""
    for node in manifest["items"].values():
        if node["type"] != "graphics":
            continue

        slug = node["slug"]
        src_dir = vault_path / slug
        dst_dir = output_path / slug

        if not src_dir.is_dir():
            print(f"  [warn] Graphics dir not found: {src_dir}")
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
            src_dir = vault_path / slug

        readme_file = _find_readme(src_dir)
        if readme_file is None:
            print(f"  [warn] README not found in: {src_dir}")
            continue

        content = readme_file.read_text(encoding="utf-8")
        html_body = md(content)

        nav_html = _build_nav(node, items)

        html = html_body + "\n" + nav_html

        out_file = output_path / node["content_path"].lstrip("/")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html, encoding="utf-8")

    print("  [readme] Home pages parsed.")


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
                    from manifest import slugify
                    if slugify(entry.name) == p:
                        found = entry
                        break
        if found:
            parent_dir = found
        else:
            return None

    if not parent_dir.is_dir():
        return None

    from manifest import slugify
    for entry in parent_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".md":
            if entry.name.lower() == "readme.md":
                continue
            if slugify(entry.stem) == filename_slug:
                return entry

    return None


def _find_readme(directory: Path) -> Path | None:
    """Find README.md (case-insensitive) in a directory."""
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() == "readme.md":
            return entry
    return None


def _build_nav(dir_node: dict, items: dict) -> str:
    """Build an HTML navigation fragment from a directory node's children.

    Produces a <nav> with links to child files and child directories.
    Graphics nodes are skipped.
    """
    children_ids = dir_node.get("children", [])
    if not children_ids:
        return ""

    file_links = []
    dir_links = []

    for child_id in children_ids:
        child = items.get(child_id)
        if child is None or child["type"] == "graphics":
            continue

        href = child["content_path"]
        title = child["title"]

        if child["type"] == "file":
            file_links.append(f'  <li><a href="{href}">{title}</a></li>')
        elif child["type"] == "directory":
            dir_links.append(f'  <li><a href="{href}">{title}</a></li>')

    parts = []

    if dir_links:
        parts.append("<nav>")
        parts.append("<h3>Sections</h3>")
        parts.append("<ul>")
        parts.extend(dir_links)
        parts.append("</ul>")
        parts.append("</nav>")

    if file_links:
        if not dir_links:
            parts.append("<nav>")
        else:
            parts.append("")
        parts.append("<h3>Pages</h3>")
        parts.append("<ul>")
        parts.extend(file_links)
        parts.append("</ul>")
        if not dir_links:
            parts.append("</nav>")
        else:
            parts.append("</nav>")

    return "\n".join(parts)


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
    md = create_parser(manifest)

    # Job 1: Copy graphics
    copy_graphics(manifest, vault_path, output_path)

    # Job 2: Parse file content pages
    parse_file_pages(manifest, vault_path, output_path, md)

    # Job 3: Parse README home pages with auto-nav
    parse_readme_pages(manifest, vault_path, output_path, md)
