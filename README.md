# Your Second Brain At Your Finger Tips
⚡️ [Live Site](https://file-explore.graham-joss.workers.dev/)
⚡️ <a href="https://file-explore.graham-joss.workers.dev/" target="_blank" rel="noopener noreferrer">Live Site</a>

Convert an Obsidian note-taking vault into a deployable single-page application.

## Architecture

```
custom-parse/   → Python build tool (Obsidian vault → HTML + manifest)
file-explore/   → Vanilla JS SPA  (reads manifest.json + content-store/ at runtime)
```

**Data flow:** the build tool writes into `file-explore/content-store/` and `file-explore/manifest.json`. The SPA is the deployable unit; `custom-parse/` never ships.

## Prerequisites

- **Python 3.12+** with a virtual environment in `custom-parse/.venv`
- **Node.js** (for `npx wrangler`)
- **mistune** — `cd custom-parse && uv venv && uv pip install mistune`

## Quick Start

```sh
make dev                        # build vault + start local server
```

Open `http://localhost:8788` in your browser.

## Makefile Usage

All commands are run from the repo root.

| Command | What it does |
|---------|-------------|
| `make build` | Parse the vault into HTML fragments and generate `manifest.json` |
| `make serve` | Start the Wrangler local dev server |
| `make deploy` | Deploy the SPA to Cloudflare Workers |
| `make dev` | **Build + serve** — full local development workflow |
| `make ship` | **Build + deploy** — build then push to production |
| `make clean` | Remove generated `content-store/` and `manifest.json` |
| `make help` | List all available targets |

### Custom vault path

By default the build targets use `~/Obsidian_Vault`. Override with:

```sh
make build VAULT=~/path/to/other_vault
make dev   VAULT=~/Documents/my_notes
```

### Typical workflows

```sh
# Iterating on CSS/JS only (vault hasn't changed)
make serve

# Full rebuild + local preview
make dev

# Ship to production
make ship

# Nuke and rebuild from scratch
make clean build
```

## Deployment

Target: **Cloudflare Workers** with static assets.

- Config: `file-explore/wrangler.jsonc`
- SPA fallback is handled via `assets.not_found_handling: "single-page-application"`
- Local dev: `make serve` (runs `npx wrangler dev`)
- Production deploy: `make deploy` (runs `npx wrangler deploy`)
