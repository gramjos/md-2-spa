/**
 * notes/content-store.js
 * Client-side manifest loader and content fetcher.
 */
const CONTENT_BASE = '/try1_ready_2_serve';
// const CONTENT_BASE = '/Obsidian_Vault_ready_2_serve';

const MANIFEST_URL = `${CONTENT_BASE}/manifest.json`;

let manifestPromise;
let contentBase = CONTENT_BASE;
const htmlCache = new Map();

export function loadManifest() {
    // Return existing promise or create a new one that caches the result
    return manifestPromise ||= (async () => {
        const res = await fetch(MANIFEST_URL);
        if (!res.ok) throw new Error(`Manifest fetch failed: ${res.status}`);
        
        const data = await res.json();
        if (data?.publicPath) contentBase = normaliseBasePath(data.publicPath);
        return data;
    })();
}

export async function resolveNode(segments) {
    const manifest = await loadManifest();
    const cleanSegments = segments.filter(Boolean);
    
    if (!cleanSegments.length) return { node: manifest.root, kind: 'directory' };
    
    const result = walk(manifest.root, cleanSegments);
    if (!result) throw new Error('Not Found');
    return result;
}

export async function fetchHtml(relativePath) {
    const path = relativePath.replace(/^\/+/, '');
    if (htmlCache.has(path)) return htmlCache.get(path);

    const promise = (async () => {
        const url = buildContentUrl(path);
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTML fetch failed: ${res.status}`);
        return rewriteRelativeUrls(await res.text(), path);
    })();

    htmlCache.set(path, promise);
    return promise.catch(err => { htmlCache.delete(path); throw err; });
}

function walk(node, segments) {
    if (!segments.length) return { node, kind: 'directory' };
    const [head, ...rest] = segments;
    
    const dir = node.directories?.find(e => e.slug === head);
    if (dir) return walk(dir, rest);
    
    const file = node.files?.find(e => e.slug === head);
    if (file && !rest.length) return { node: file, kind: 'file' };
    
    return null;
}

export const toNotesHref = (slug) => slug ? `/notes/${slug}` : '/notes';

function buildContentUrl(path) {
    return `${contentBase}/${path}`.replace(/\/+/g, '/');
}

export function buildSourceUrl(sourcePath) {
    return `${contentBase}/${sourcePath}`.replace(/\/+/g, '/');
}

function rewriteRelativeUrls(html, path) {
    if (!contentBase) return html;
    const prefix = `${contentBase}/${path.split('/').slice(0, -1).join('/')}`.replace(/\/+/g, '/');
    
    const replacer = (_, attr, url, q) => {
        const clean = url.trim();
        if (/^(?:[a-z]+:|data:|\/)/i.test(clean)) return _;
        return `${attr}${prefix}/${clean.replace(/^\.\//, '')}${q}`;
    };

    return html
        .replace(/(src\s*=\s*["'])([^"'?#]+)(["'])/gi, replacer)
        .replace(/(data-excalidraw-src\s*=\s*["'])([^"'?#]+)(["'])/gi, replacer);
}

const normaliseBasePath = (v) => (v || CONTENT_BASE).trim().replace(/^\/?/, '/').replace(/\/+$/, '');
