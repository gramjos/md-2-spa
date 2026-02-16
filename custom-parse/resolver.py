"""
Resolution logic for the Obsidian parser.

Handles building indexes from the manifest and resolving wiki-links and image embeds.
"""

from manifest import slugify

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
