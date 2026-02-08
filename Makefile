# md-2-spa/Makefile
# ──────────────────────────────────────────────

VAULT       ?= $(HOME)/Obsidian_Vault
SPA_DIR     := file-explore
PARSE_DIR   := custom-parse
VENV        := $(PARSE_DIR)/.venv/bin/activate
CONTENT     := $(SPA_DIR)/content-store
MANIFEST    := $(SPA_DIR)/manifest.json

.PHONY: build serve deploy dev ship clean help

## build   — Parse vault → HTML + manifest
build:
	cd $(PARSE_DIR) && source $(CURDIR)/$(VENV) && python build.py $(VAULT) --spa ../$(SPA_DIR)

## serve   — Start Wrangler local dev server
serve:
	cd $(SPA_DIR) && npx wrangler dev

## deploy  — Deploy SPA to Cloudflare Pages
deploy:
	cd $(SPA_DIR) && npx wrangler pages deploy .

## dev     — Build then serve locally
dev: build serve

## ship    — Build then deploy to production
ship: build deploy

## clean   — Wipe generated content (safe — build.py recreates it)
clean:
	rm -rf $(CONTENT) $(MANIFEST)

## help    — Show available targets
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'
