"""
Parser for Obsidian Vault → HTML conversion.

Facade for the refactored parser modules.
The logic has been split into:
  - resolver.py: link/asset resolution logic
  - renderer.py: mistune configuration
  - pipeline.py: file processing and orchestration
"""

from pipeline import parse_vault

__all__ = ["parse_vault"]
