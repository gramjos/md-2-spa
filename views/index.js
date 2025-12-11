// View functions stay modular so routing just chooses among them.
import { resolveNode, fetchHtml, toNotesHref } from '../notes/content-store.js';
import { codeBlock, escapeHtml } from '../utils/rendering.js';
import { initializeExcalidrawEmbeds } from '../utils/excalidraw.js';

export function renderHome(ctx) {
    document.title = 'Deep-Linked SPA Example';
    ctx.mount.innerHTML = `
        <section>
            <h1>Deep-Linked SPA from a Manifest</h1>
            <p>
                This single-page app demonstrates how to build a routable note system
                that generates itself from a manifest file. The entire site structure
                comes from <code>manifest.json</code> and renders dynamically.
            </p>
            
            <h2>How It Works</h2>
            <ol>
                <li><strong>Build Process:</strong> Python scripts scan a folder of markdown files and generate:
                    <ul>
                        <li><code>manifest.json</code> – describes the entire folder structure, files, and metadata</li>
                        <li>HTML fragments for each markdown file</li>
                    </ul>
                </li>
                <li><strong>Content Store:</strong> <code>content-store.js</code> loads the manifest and resolves paths to content</li>
                <li><strong>Router:</strong> <code>router.js</code> intercepts navigation and matches URLs to views</li>
                <li><strong>Views:</strong> Render functions fetch HTML fragments and display them with breadcrumbs</li>
            </ol>
            
            <h2>Key Features</h2>
            <ul>
                <li>✅ Every page is deep-linkable with clean URLs</li>
                <li>✅ No page reloads – all navigation is client-side via History API</li>
                <li>✅ Breadcrumb navigation auto-generates from manifest structure</li>
                <li>✅ Back/forward browser buttons work correctly</li>
                <li>✅ Content structure defined entirely by your files</li>
            </ul>
            
            <p>
                <strong>Start exploring:</strong> Visit <a href="/notes">Notes</a> to see the manifest-driven navigation in action.
                Each note you click demonstrates client-side routing with deep-linking support.
            </p>

            <h2>Current Route</h2>
            <p>You're viewing: <code>${escapeHtml(ctx.location.path)}</code></p>
            ${codeBlock(`// View functions receive routing context
function renderHome(ctx) {
  // ctx.location.path = current URL path
  // ctx.params = extracted route parameters
  // ctx.mount = DOM node to render into
  ctx.mount.innerHTML = '<h1>Hello</h1>';
}`)}
        </section>
    `;
}


export function renderNotes(ctx) {
    renderNotesPath(ctx, []);
}

export function renderNoteDetail(ctx) {
    const slugParam = ctx.params.path || '';
    const segments = slugParam.split('/').map((segment) => segment.trim()).filter(Boolean);
    renderNotesPath(ctx, segments);
}

function renderNotesPath(ctx, segments) {
    const requestPath = ctx.location.path;
    ctx.mount.innerHTML = renderNotesLoading();

    resolveNode(segments)
        .then(async (result) => {
            if (ctx.location.path !== requestPath) return;

            if (result.kind === 'directory') {
                const readmeHtml = await fetchHtml(result.node.readme.html);
                if (ctx.location.path !== requestPath) return;
                document.title = directoryTitle(result.node);
                ctx.mount.innerHTML = buildDirectoryMarkup(result.node, readmeHtml);
                // Initialize any Excalidraw embeds in the content
                initializeExcalidrawEmbeds();
                return;
            }

            const fileHtml = await fetchHtml(result.node.html);
            if (ctx.location.path !== requestPath) return;
            document.title = fileTitle(result.node);
            ctx.mount.innerHTML = buildFileMarkup(result.node, fileHtml);
            // Initialize any Excalidraw embeds in the content
            initializeExcalidrawEmbeds();
        })
        .catch((error) => {
            console.error(error);
            if (ctx.location.path !== requestPath) return;
            document.title = 'Notes not found · Deep-Linked SPA';
            ctx.mount.innerHTML = renderNotesError(segments);
        });
}

function buildDirectoryMarkup(node, readmeHtml) {
    return `
        <section class="notes-view">
            ${renderBreadcrumbs(node.breadcrumbs, node.title, node.slugPath)}
            <header class="notes-header">
                <h1>${escapeHtml(node.title)}</h1>
            </header>
            ${renderDirectoryLists(node)}
            <article class="notes-content">${readmeHtml}</article>
        </section>
    `;
}

function buildFileMarkup(node, fileHtml) {
    const breadcrumbs = node.breadcrumbs || [];
    const parentCrumb = breadcrumbs[breadcrumbs.length - 1] || null;
    const backHref = parentCrumb ? toNotesHref(parentCrumb.slugPath) : '/notes';
    const backLabel = parentCrumb ? parentCrumb.title : 'Notes';
    return `
        <section class="notes-view">
            ${renderBreadcrumbs(breadcrumbs, node.title, node.slugPath)}
            <a class="notes-backlink" href="${backHref}">← Back to ${escapeHtml(backLabel)}</a>
            <h1>${escapeHtml(node.title)}</h1>
            <article class="notes-content">${fileHtml}</article>
        </section>
    `;
}

function renderDirectoryLists(node) {
    const sections = [];
    if (Array.isArray(node.directories) && node.directories.length > 0) {
        sections.push(renderDirectoryPanel('Directories', node.directories));
    }
    if (Array.isArray(node.files) && node.files.length > 0) {
        sections.push(renderDirectoryPanel('Files', node.files));
    }
    if (sections.length === 0) {
        return '<p class="muted">No additional content in this section yet.</p>';
    }
    return `<div class="notes-directory-lists">${sections.join('')}</div>`;
}

function renderDirectoryPanel(label, items) {
    return `
        <div class="notes-directory-panel">
            <h2>${escapeHtml(label)}</h2>
            <ul>
                ${items.map((item) => `
                    <li><a href="${toNotesHref(item.slugPath)}">${escapeHtml(item.title)}</a></li>
                `).join('')}
            </ul>
        </div>
    `;
}

function renderBreadcrumbs(trail, currentTitle, currentSlugPath) {
    const crumbs = Array.isArray(trail) ? [...trail] : [];
    if (currentTitle) {
        crumbs.push({ title: currentTitle, slugPath: currentSlugPath, current: true });
    }
    if (crumbs.length === 0) {
        return '';
    }

    const parts = crumbs.map((crumb) => {
        if (crumb.current) {
            return `<span aria-current="page">${escapeHtml(crumb.title)}</span>`;
        }
        return `<a href="${toNotesHref(crumb.slugPath)}">${escapeHtml(crumb.title)}</a>`;
    });

    const joined = parts.map((part, index) => {
        if (index === 0) return part;
        return `<span class="notes-breadcrumbs__sep">/</span>${part}`;
    }).join('');

    return `<nav class="notes-breadcrumbs" aria-label="Breadcrumb">${joined}</nav>`;
}

function renderNotesLoading(message = 'Loading notes…') {
    return `
        <section class="notes-view">
            <p>${escapeHtml(message)}</p>
        </section>
    `;
}

function renderNotesError(segments) {
    const target = segments.length ? segments.join('/') : 'notes home';
    return `
        <section class="notes-view">
            <h1>We could not find that note</h1>
            <p>No content exists for <code>${escapeHtml(target)}</code>.</p>
            <p><a href="/notes">Return to the notes home</a> to browse available content.</p>
        </section>
    `;
}

function directoryTitle(node) {
    return node.slugPath
        ? `${node.title} · Notes · Deep-Linked SPA`
        : 'Notes · Deep-Linked SPA';
}

function fileTitle(node) {
    return `${node.title} · Notes · Deep-Linked SPA`;
}

export function renderNotFound(ctx) {
    document.title = '404 · Deep-Linked SPA';
    ctx.mount.innerHTML = `
        <section>
            <h1>Page Not Found</h1>
            <p>The path <code>${escapeHtml(ctx.location.path)}</code> does not match any registered route.</p>
            <p><a href="/">Return home</a> or browse <a href="/notes">Notes</a>.</p>
        </section>
    `;
}
