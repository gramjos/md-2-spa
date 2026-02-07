# md-2-spa

Convert an Obsidian vault into a static single-page application and deploy it to Cloudflare Pages.

```
┌─────────────────┐      ┌───────────────┐      ┌──────────────────┐
│  Obsidian Vault  │─────▶│  custom-parse  │─────▶│   file-explore   │
│   (.md files)    │      │  (Python CLI)  │      │   (Vanilla SPA)  │
└─────────────────┘      └───────────────┘      └──────────────────┘
                           generates:             serves:
                           • m.json (manifest)    • SPA shell (index.html)
                           • HTML fragments       • JS router + file-tree
                           • graphics assets      • content-store/ (content)
```

---

## Prerequisites

- **Python 3.11+** with `mistune` installed
- **Node.js 18+** (for local preview with `npx serve` or `npx wrangler`)
- A **Cloudflare** account (for deployment)

```bash
# Install the Python dependency
pip install mistune

# Install Wrangler globally (optional, for deployment)
npm install -g wrangler
```

---

## Project Structure

```
md-2-spa/
├── custom-parse/           # Python build pipeline
│   ├── build.py            # CLI entry point
│   ├── manifest.py         # Vault walker → m.json
│   └── parser.py           # Markdown → HTML (mistune + Obsidian plugins)
│
├── file-explore/           # Static SPA (deploy this)
│   ├── index.html          # App shell
│   ├── m.json              # ← generated manifest
│   ├── style.css
│   ├── wrangler.jsonc      # Cloudflare Pages config
│   ├── serve.json          # Local dev server config
│   ├── _redirects
│   ├── js/
│   │   ├── app.js          # Bootstrap
│   │   ├── router.js       # SPA router (History API)
│   │   ├── file-tree.js    # Sidebar builder
│   │   ├── mobile-menu.js  # Responsive menu
│   │   └── theme-toggle.js # Dark/light mode
│   └── content-store/      # ← generated HTML + graphics
│       ├── readme.html
│       ├── about.html
│       ├── graphics/
│       └── nature/
│           ├── README.html
│           └── desert.html
```

---

## Usage

### 1. Build: Vault → SPA

From the `custom-parse/` directory, point `build.py` at your vault and the SPA root:

```bash
cd custom-parse

# Basic — output directly into the SPA
python build.py /path/to/your/vault --spa ../file-explore

# With a custom title for the root landing page
python build.py /path/to/your/vault --spa ../file-explore --title "My Garden"
```

This does two things:
1. Writes HTML fragments + graphics into `file-explore/content-store/`
2. Writes the manifest to `file-explore/m.json`

**Example with a real vault:**

```bash
python build.py ~/Documents/my_obsidian_vault --spa ../file-explore --title "Brain Dump"
```

```
[1/2] Generating manifest from: /Users/you/Documents/my_obsidian_vault
  Manifest written to /Users/you/Computation/md-2-spa/file-explore/m.json (12 nodes)
[2/2] Parsing vault → HTML
  [graphics] Assets copied.
  [files] Content pages parsed.
  [readme] Home pages parsed.
SPA ready at: /Users/you/Computation/md-2-spa/file-explore
Done.
```

### Alternative: Standalone output (no SPA)

If you just want the HTML fragments without wiring them into the SPA:

```bash
python build.py /path/to/vault -o ./my-output
```

This writes everything (manifest + HTML + graphics) into `./my-output/`.

---

### 2. Preview Locally

#### Option A: `npx serve` (quick)

```bash
cd ../file-explore
npx serve -s -l 3000
```

Open [http://localhost:3000](http://localhost:3000)

> The `-s` flag enables SPA mode — all routes fall back to `index.html`. The `serve.json` config ensures `content-store/` files are served directly.

#### Option B: `wrangler pages dev` (matches production)

```bash
cd ../file-explore
npx wrangler pages dev .
```

This runs the Cloudflare Pages runtime locally, so SPA fallback and asset serving behave exactly like production.

Open [http://localhost:8788](http://localhost:8788)

---

### 3. Deploy to Cloudflare Pages

#### First-time setup

```bash
# Authenticate with Cloudflare (one-time)
npx wrangler login

# Create the Pages project
npx wrangler pages project create my-digi-garden
```

#### Deploy

```bash
cd file-explore
npx wrangler pages deploy .
```

```
✨ Deployment complete!
  Project:  my-digi-garden
  URL:      https://my-digi-garden.pages.dev
```

That's it. The `wrangler.jsonc` is already configured:

```jsonc
{
  "name": "file-explore",
  "compatibility_date": "2026-02-06",
  "assets": {
    "directory": "./",
    "not_found_handling": "single-page-application"
  }
}
```

The `"not_found_handling": "single-page-application"` setting tells Cloudflare to serve `index.html` for any unmatched route, which is what makes the SPA routing work.

#### Custom domain (optional)

```bash
npx wrangler pages project edit my-digi-garden --domain garden.yourdomain.com
```

Or configure it in the Cloudflare dashboard under **Pages → your project → Custom domains**.

---

## Full Workflow Example

End-to-end from vault to live site:

```bash
# 1. Install dependency
pip install mistune

# 2. Build vault into SPA
cd custom-parse
python build.py ~/Documents/my_obsidian_vault --spa ../file-explore --title "My Notes"

# 3. Preview locally
cd ../file-explore
npx wrangler pages dev .
# → open http://localhost:8788

# 4. Deploy
npx wrangler pages deploy .
# → https://my-digi-garden.pages.dev
```

### Rebuild after vault changes

Just re-run the build command. It cleans `content-store/` before writing so stale files don't linger:

```bash
cd custom-parse
python build.py ~/Documents/my_obsidian_vault --spa ../file-explore
```

---

## Vault Requirements

Your Obsidian vault must follow two structural rules:

1. **README signal** — Only directories containing a `README.md` are eligible for conversion. The README becomes the directory's landing page.
2. **Graphics exception** — Directories named exactly `graphics` are exempt from needing a README. They hold images/media.

```
my_vault/
├── README.md           ✅ Root landing page
├── about.md            ✅ Converted (root has README)
├── graphics/           ✅ Media assets (exempt from README rule)
│   └── logo.png
├── physics/
│   ├── README.md       ✅ Physics landing page
│   └── gravity.md      ✅ Converted
├── poetry/
│   └── haiku.md        ❌ Skipped (no README.md in poetry/)
└── .obsidian/          ⊘ Ignored automatically
```

### Supported Markdown Syntax

| Syntax | Example | Output |
|--------|---------|--------|
| Headings | `# Title` | `<h1>Title</h1>` |
| Bold | `**bold**` | `<strong>bold</strong>` |
| Italic | `*italic*` | `<em>italic</em>` |
| Inline code | `` `code` `` | `<code>code</code>` |
| Wiki-link | `[[Page Name]]` | `<a href="...">Page Name</a>` |
| Wiki-link (aliased) | `[[page\|Display]]` | `<a href="...">Display</a>` |
| Image embed | `![[photo.png]]` | `<img src="graphics/photo.png">` |
| Standard link | `[text](url)` | `<a href="url">text</a>` |
| Standard image | `![alt](url)` | `<img src="url" alt="alt">` |
| Horizontal rule | `---` | `<hr>` |

---

## CLI Reference

```
usage: build.py [-h] [-o OUTPUT] [--spa SPA_ROOT] [--title TITLE] vault_path

Build static HTML from an Obsidian vault.

positional arguments:
  vault_path            Path to the root of the Obsidian vault.

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                         Output directory (default: try_hosting_Vault_ready_2_serve).
  --spa SPA_ROOT        Path to the file-explore SPA root. When set, content
                         is written to <SPA_ROOT>/content-store/ and the
                         manifest to <SPA_ROOT>/m.json.
  --title TITLE         Title for the root landing page (default: 'Digi Garden').
```
