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
  - $inline math$  → <span class="math">\\(...\\)</span> (rendered by KaTeX on client)
  - $$display math$$ → <div class="math">\\[...\\]</div> (rendered by KaTeX on client)
"""

import re
import shutil
from pathlib import Path

import mistune
from mistune import escape as escape_text

from frontmatter import extract_frontmatter


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

    Obsidian embeds may include a directory prefix
    (e.g. "graphics/ani3.gif") — we strip it and look up by
    basename only, since the asset_index is keyed on filenames.

    e.g. "hap.png"           → "/moss/graphics/hap.png"
         "graphics/ani3.gif" → "/graphics/ani3.gif"
         "img.png"           → "/graphics/img.png"
    """
    filename = filename.strip()
    # Strip any directory prefix (Obsidian sometimes includes "graphics/")
    basename = filename.rsplit("/", 1)[-1] if "/" in filename else filename
    if basename in asset_index:
        return asset_index[basename] + basename
    # Fallback: assume root graphics
    return f"/graphics/{basename}"


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
        # Strip Obsidian pipe suffix (e.g. "img.png|350" → "img.png")
        if "|" in filename:
            filename = filename.split("|", 1)[0]
        src = resolve_image_embed(filename, md.renderer._asset_index)
        # Use basename (no directory prefix) for alt text
        basename = filename.rsplit("/", 1)[-1] if "/" in filename else filename
        alt = basename.rsplit(".", 1)[0] if "." in basename else basename
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

def slugify_heading(text: str) -> str:
    """Convert heading text to a URL-friendly slug for anchor IDs.

    Strips HTML tags, lowercases, replaces non-alphanumeric runs with
    hyphens, and trims leading/trailing hyphens.

    e.g. "Practice Problem" → "practice-problem"
         "What is O(n log n)?" → "what-is-on-log-n"
    """
    # Strip any inline HTML tags
    slug = re.sub(r'<[^>]+>', '', text)
    slug = slug.lower()
    # Replace non-alphanumeric (keep hyphens) with hyphens
    slug = re.sub(r'[^a-z0-9-]+', '-', slug)
    # Collapse multiple hyphens
    slug = re.sub(r'-{2,}', '-', slug)
    return slug.strip('-')


def create_parser(manifest: dict) -> mistune.Markdown:
    """Create a configured mistune Markdown parser with Obsidian plugins.

    The manifest indexes are attached to the renderer so plugins can
    resolve links and images at render time.
    """
    md = mistune.create_markdown(
        escape=False,
        plugins=['math', plugin_wiki_embed, plugin_wiki_link],
    )

    # Sanitize: strip dangerous raw HTML tags after rendering
    _original_call = md.__class__.__call__

    def _sanitized_call(self, text):
        html = _original_call(self, text)
        # Remove <style>, <script>, <iframe> tags and their content
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove on* event handler attributes
        html = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', '', html, flags=re.IGNORECASE)
        html = re.sub(r"\s+on\w+\s*=\s*'[^']*'", '', html, flags=re.IGNORECASE)
        return html

    import types
    md.__call__ = types.MethodType(_sanitized_call, md)

    # Attach manifest indexes to the renderer for link/image resolution
    title_index = build_title_index(manifest)
    slug_index = build_slug_index(manifest)
    asset_index = build_asset_index(manifest)

    md.renderer._title_index = title_index
    md.renderer._slug_index = slug_index
    md.renderer._asset_index = asset_index

    # Override block_code renderer to add copy-to-clipboard button
    def block_code(code, info=None):
        escaped = escape_text(code)
        if info:
            lang = info.split()[0]
            lang_attr = f' class="language-{lang}"'
            lang_label = f'<span class="code-lang">{lang}</span>'
        else:
            lang_attr = ''
            lang_label = ''
        return (
            f'<div class="code-block">'
            f'{lang_label}'
            f'<button class="copy-btn" aria-label="Copy code">Copy</button>'
            f'<pre><code{lang_attr}>{escaped}</code></pre>'
            f'</div>\n'
        )

    md.renderer.block_code = block_code

    # Override heading renderer to add slugified id attributes for anchor links
    # Tracks seen slugs per-render to deduplicate (e.g. "foo", "foo-1", "foo-2")
    heading_slug_counts: dict[str, int] = {}

    def heading(text, level, **attrs):
        slug = slugify_heading(text)
        if slug in heading_slug_counts:
            heading_slug_counts[slug] += 1
            slug = f'{slug}-{heading_slug_counts[slug]}'
        else:
            heading_slug_counts[slug] = 0
        return f'<h{level} id="{slug}"><a class="heading-anchor" href="#{slug}" data-link>{text}</a></h{level}>\n'

    md.renderer.heading = heading

    # ── Math rendering overrides ──────────────────────────────────────
    # Mistune 3.x math plugin issues:
    #   1. Block math ($$...$$) ONLY works multi-line; single-line $$x$$
    #      falls through to inline, producing garbled output.
    #   2. Block renderer keeps raw $$ delimiters; inline uses \( \).
    #
    # Fix: override both renderers to emit \( \) and \[ \],
    # and register an inline pattern for single-line $$...$$.

    # Override renderers to use consistent \( \) and \[ \] delimiters
    def render_inline_math(renderer, text):
        return f'<span class="math">\\({text}\\)</span>'

    def render_block_math(renderer, text):
        return f'<div class="math">\\[{text}\\]</div>\n'

    md.renderer.register('inline_math', render_inline_math)
    md.renderer.register('block_math', render_block_math)

    # Handle single-line $$...$$ (mistune's block pattern requires newlines)
    INLINE_DISPLAY_PATTERN = r'\$\$(?P<display_math_text>.+?)\$\$'

    def parse_inline_display_math(inline, m, state):
        text = m.group('display_math_text')
        state.append_token({'type': 'block_math', 'raw': text})
        return m.end()

    md.inline.register(
        'inline_display_math',
        INLINE_DISPLAY_PATTERN,
        parse_inline_display_math,
        before='inline_math',   # must match before single-$ inline math
    )

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


def _resolve_slug_to_dir(vault_path: Path, slug: str) -> Path | None:
    """Resolve a slugified path back to the real filesystem directory.

    Walks each segment of the slug, matching against actual directory names
    via slugify() to handle spaces, mixed case, etc.
    e.g. slug='moss/moss-1/graphics' → vault_path/'moss'/'moss 1'/'graphics'
    """
    from manifest import slugify

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
