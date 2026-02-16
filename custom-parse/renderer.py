"""
Renderer for the Obsidian parser.

Configures Mistune with custom plugins and renderers for:
- Obsidian wiki-links and image embeds
- Math (KaTeX compatible)
- Syntax highlighting
"""

import re
import types
import mistune
from mistune import escape as escape_text

import resolver

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
        src = resolver.resolve_image_embed(filename, md.renderer._asset_index)
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
        href, display = resolver.resolve_wiki_link(
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
        hard_wrap=True,
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

    md.__call__ = types.MethodType(_sanitized_call, md)

    # Attach manifest indexes to the renderer for link/image resolution
    title_index = resolver.build_title_index(manifest)
    slug_index = resolver.build_slug_index(manifest)
    asset_index = resolver.build_asset_index(manifest)

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
