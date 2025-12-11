// Router primitives keep history wiring isolated from view code.
export function createRoute(template, render) {
    // Compile templates like "/guides/:slug" into executable matchers.
    if (template === '*') {
        return {
            template,
            render,
            isCatchAll: true,
            match: () => ({ params: {} }),
        };
    }
    const pattern = new URLPattern({ pathname: template });
    return {
        template,
        render,
        isCatchAll: false,
        match: (path) => {
            
            const match = pattern.exec({ pathname: path });
            // URLPattern returns parameters in match.pathname.groups
            return match ? { params: match.pathname.groups || {} } : null;
        },
    };
}

export function createRouter({ mountNode, routes }) {
    const baseUrl = new URL(window.originalHref || window.location.href);
    const baseDir = new URL('.', baseUrl).pathname.replace(/\/$/, '');
    const navLinks = Array.from(document.querySelectorAll('.site-nav a'));
    const state = { currentPath: null };

    const normalRoutes = routes.filter((route) => !route.isCatchAll);
    const fallbackRoute = routes.find((route) => route.isCatchAll);

    // Hijack eligible anchor clicks so navigation stays client-side.
    const onLinkClick = (event) => {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const anchor = event.target.closest('a[href]');
        if (!anchor) return;
        if (anchor.target && anchor.target !== '_self') return;
        if (anchor.hasAttribute('download') || anchor.getAttribute('rel') === 'external') return;
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('#')) return;

        const resolved = new URL(anchor.href, baseUrl);
        if (resolved.origin !== baseUrl.origin) return;

        const appPath = toAppPath(resolved.pathname);
        if (appPath == null) return;

        event.preventDefault();
        navigate(appPath + resolved.search + resolved.hash);
    };

    // Browser history changes land here via the popstate event.
    const onPopState = () => onLocationChange({ triggeredByPop: true });

    // Diff the new URL, update nav state, and render the matching view.
    const onLocationChange = ({ triggeredByPop = false } = {}) => {
        const currentUrl = new URL(window.location.href);
        const path = toAppPath(currentUrl.pathname);
        if (path == null) {
            console.warn('Ignoring navigation outside the SPA base path.');
            return;
        }

        if (!triggeredByPop && state.currentPath === path && currentUrl.search === '' && currentUrl.hash === '') {
            return;
        }

        state.currentPath = path;
        const locationState = {
            path,
            search: currentUrl.search,
            hash: currentUrl.hash,
            url: currentUrl,
        };

        updateActiveNav(locationState);
        resolveRoute(path, locationState);
    };

    // Find the first matching route, otherwise fall back.
    const resolveRoute = (path, locationState) => {
        for (const route of normalRoutes) {
            const match = route.match(path);
            if (match) {
                renderRoute(route, match.params, locationState);
                return;
            }
        }
        if (fallbackRoute) {
            renderRoute(fallbackRoute, { path }, locationState);
        }
    };

    // Execute the render function with a minimal context object.
    const renderRoute = (route, params, locationState) => {
        const context = {
            mount: mountNode,
            params,
            location: locationState,
            navigate,
            route: route.template,
        };
        route.render(context);
    };

    // Reflect the current route in the persistent nav menu.
    const updateActiveNav = (locationState) => {
        navLinks.forEach((link) => {
            const resolved = new URL(link.getAttribute('href'), baseUrl);
            const linkPath = toAppPath(resolved.pathname);
            const isActive = linkPath === '/'
                ? locationState.path === '/'
                : locationState.path === linkPath || locationState.path.startsWith(linkPath + '/');
            if (isActive) {
                link.dataset.active = 'true';
            } else {
                delete link.dataset.active;
            }
        });
    };

    // Drive both pushState and replaceState with the same API.
    const navigate = (destination, { replace = false } = {}) => {
        const [pathname, suffix] = splitDestination(destination);
        if (!pathname.startsWith('/')) {
            throw new Error('Router.navigate expects an absolute path.');
        }
        const browserPath = toBrowserPath(pathname) + suffix;
        if (replace) {
            history.replaceState({}, '', browserPath);
        } else if (browserPath !== window.location.pathname + window.location.search + window.location.hash) {
            history.pushState({}, '', browserPath);
        }
        onLocationChange();
    };

    // Convert a browser pathname into an app-relative one.
    const toAppPath = (pathname) => {
        if (baseDir) {
            if (!pathname.startsWith(baseDir)) return null;
            const relative = pathname.slice(baseDir.length) || '/';
            return normalisePath(relative);
        }
        return normalisePath(pathname);
    };

    // Reverse the mapping when writing URLs back to the bar.
    const toBrowserPath = (pathname) => {
        const clean = normalisePath(pathname);
        if (baseDir) {
            return clean === '/'
                ? `${baseDir}/`
                : `${baseDir}${clean}`;
        }
        return clean;
    };

    // Strip redundant slashes while treating "/" as canonical.
    const normalisePath = (value) => {
        if (!value) return '/';
        const path = new URL(value, 'http://placeholder').pathname;
        if (path === '/index.html') return '/';
        if (path.length > 1 && path.endsWith('/')) {
            return path.replace(/\/+$/, '');
        }
        return path;
    };

    // Split any query/hash suffix from the path for push/replace.
    const splitDestination = (destination) => {
        const { pathname, search, hash } = new URL(destination, 'http://placeholder');
        return [pathname, search + hash];
    };

    return {
        start: () => {
            window.addEventListener('popstate', onPopState);
            document.addEventListener('click', onLinkClick);
            onLocationChange({ triggeredByPop: true });
        },
        navigate,
        toAppPath,
    };
}

