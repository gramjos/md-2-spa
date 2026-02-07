"""
Build pipeline for Obsidian Vault → HTML conversion.

Orchestrates:
  1. Manifest generation — walk the vault, produce the content tree
  2. Parsing — convert .md to .html using the manifest as source of truth

Usage:
    python build.py /path/to/vault
    python build.py /path/to/vault --title "My Site"
    python build.py /path/to/vault -o /path/to/output
    python build.py /path/to/vault --spa ../file-explore
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from manifest import generate_manifest
from parser import parse_vault

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = "try_hosting_Vault_ready_2_serve"
DEFAULT_MANIFEST_NAME = "manifest.json"
DEFAULT_TITLE = "Digi Garden"

# When --spa is used, content goes into <spa_root>/content-store/
# and the manifest goes into <spa_root>/manifest.json
CONTENT_STORE_DIR = "content-store"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build(vault_path: str, output_dir: str, title: str, spa_root: str | None = None) -> None:
    """Run the full build pipeline.

    If *spa_root* is provided the output is placed directly into the
    file-explore SPA:
        <spa_root>/content-store/  ← HTML fragments + graphics
        <spa_root>/manifest.json   ← manifest
    """
    vault = Path(vault_path).resolve()

    if not vault.is_dir():
        print(f"Error: '{vault_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Resolve output paths
    if spa_root:
        spa = Path(spa_root).resolve()
        output = spa / CONTENT_STORE_DIR
        manifest_dest = spa / DEFAULT_MANIFEST_NAME
    else:
        output = Path(output_dir).resolve()
        manifest_dest = output / DEFAULT_MANIFEST_NAME

    # Clean content-store so stale files don't linger
    if output.is_dir():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Generate manifest ---
    print(f"[1/2] Generating manifest from: {vault}")
    manifest = generate_manifest(str(vault), title=title)

    # Write manifest
    manifest_dest.parent.mkdir(parents=True, exist_ok=True)
    manifest_dest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Manifest written to {manifest_dest} ({len(manifest['items'])} nodes)")

    # --- Step 2: Parse vault ---
    print(f"[2/2] Parsing vault → HTML")
    parse_vault(manifest, vault, output)

    if spa_root:
        print(f"SPA ready at: {spa}")
    print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Build static HTML from an Obsidian vault."
    )
    ap.add_argument(
        "vault_path",
        help="Path to the root of the Obsidian vault.",
    )
    ap.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    ap.add_argument(
        "--spa",
        default=None,
        metavar="SPA_ROOT",
        help="Path to the file-explore SPA root. When set, content is written "
             "to <SPA_ROOT>/content-store/ and the manifest to <SPA_ROOT>/manifest.json.",
    )
    ap.add_argument(
        "--title",
        default=DEFAULT_TITLE,
        help=f"Title for the root landing page (default: '{DEFAULT_TITLE}').",
    )

    args = ap.parse_args()
    build(args.vault_path, args.output, args.title, spa_root=args.spa)


if __name__ == "__main__":
    main()
