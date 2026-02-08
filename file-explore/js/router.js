// ===== SPA Router (History API) with Named Routes =====
export class Router {
	constructor() {
		this.routes = new Map()
		this.manifest = null
		this.flatRoutes = []
		
		// Tag index: tagName → [{ title, route, type }]
		this.tagIndex = new Map()
		
		// Named route definitions: each declares its layout
		this.namedRoutes = {
			home: {
				path: '/',
				title: 'Home',
				sidebar: false,
				render: () => this.renderHome()
			},
			about: {
				path: '/about',
				title: 'About',
				sidebar: false,
				render: () => this.renderAbout()
			},
			notes: {
				path: '/notes',
				title: 'Notes',
				sidebar: true,
				render: (routeData) => this.renderNotes(routeData)
			},
			tags: {
				path: '/tags',
				title: 'Tags',
				sidebar: false,
				render: () => this.renderTagIndex()
			},
			tag: {
				path: '/tags/',
				title: 'Tag',
				sidebar: false,
				render: (tagName) => this.renderTagPage(tagName)
			}
		}
		
		this.currentNamedRoute = null
		
		window.addEventListener('popstate', () => this.handleRoute())
	}
	
	// Build routes from flat manifest structure
	buildRoutes(manifest) {
		const items = manifest.items;
		
		// Recursive helper to traverse by ID
		const traverse = (id, parentPath = '') => {
			const item = items[id];
			if (!item) return;

			// Skip graphics nodes — they hold assets, not pages
			if (item.type === 'graphics') return;

			const subroute = this.pathToSubRoute(item.content_path)
			const route = '/notes' + subroute
			
			const tags = item.metadata?.tags ?? []
			
			this.routes.set(route, {
				title: item.title,
				type: item.type,
				contentPath: item.content_path,
				parentPath: parentPath,
				namedRoute: 'notes',
				tags: tags
			})
			
			this.flatRoutes.push({
				route,
				title: item.title,
				type: item.type,
				contentPath: item.content_path
			})
			
			// Index tags
			if (Array.isArray(tags)) {
				for (const tag of tags) {
					const key = String(tag).toLowerCase()
					if (!this.tagIndex.has(key)) this.tagIndex.set(key, [])
					this.tagIndex.get(key).push({ title: item.title, route, type: item.type })
				}
			}
			
			// Recurse through children IDs
			if (item.children && item.children.length > 0) {
				item.children.forEach(childId => traverse(childId, route))
			}
		}

		// Start traversal from the rootId
		if (manifest.rootId) {
			traverse(manifest.rootId)
		}
	}
	
	// Convert content path to sub-route (e.g., /nature/README.html -> /nature)
	pathToSubRoute(contentPath) {
		if (!contentPath) return ''
		return contentPath
			.replace(/\.html$/, '')
			.replace(/\/README$/i, '')
			.replace(/\/readme$/i, '')
			|| ''
	}
	
	// Legacy helper kept for tree building
	pathToRoute(contentPath) {
		const sub = this.pathToSubRoute(contentPath)
		return '/notes' + sub
	}
	
	// Navigate to a route
	navigate(route, replace = false) {
		if (replace) {
			history.replaceState({ route }, '', route)
		} else {
			history.pushState({ route }, '', route)
		}
		this.handleRoute()
	}
	
	// Get current route from pathname
	getCurrentRoute() {
		const path = window.location.pathname
		return path || '/'
	}
	
	// Resolve which named route is active
	resolveNamedRoute(path) {
		if (path === '/') return 'home'
		if (path === '/about') return 'about'
		if (path === '/tags') return 'tags'
		if (path.startsWith('/tags/')) return 'tag'
		if (path === '/notes' || path.startsWith('/notes/') || path.startsWith('/notes?')) return 'notes'
		return null
	}
	
	// Handle route change
	async handleRoute() {
		const route = this.getCurrentRoute()
		const namedRouteName = this.resolveNamedRoute(route)
		
		// Reset scroll position on navigation
		document.getElementById('content-display').scrollTop = 0
		
		// Apply layout for the named route
		this.applyLayout(namedRouteName)
		this.updateTopNav(namedRouteName)
		
		if (namedRouteName === 'home') {
			this.namedRoutes.home.render()
			document.title = 'Home - Doc.'
			return
		}
		
		if (namedRouteName === 'about') {
			this.namedRoutes.about.render()
			document.title = 'About - Doc.'
			return
		}
		
		if (namedRouteName === 'tags') {
			this.namedRoutes.tags.render()
			this.updateTagsBar(null)
			document.title = 'Tags - Doc.'
			const breadcrumb = document.getElementById('breadcrumb')
			breadcrumb.innerHTML = `<a href="/" data-link>Home</a><span>/</span>Tags`
			return
		}
		
		if (namedRouteName === 'tag') {
			const tagName = decodeURIComponent(route.replace('/tags/', ''))
			this.namedRoutes.tag.render(tagName)
			this.updateTagsBar(null)
			document.title = `Tag: ${tagName} - Doc.`
			const breadcrumb = document.getElementById('breadcrumb')
			breadcrumb.innerHTML = `<a href="/" data-link>Home</a><span>/</span><a href="/tags" data-link>Tags</a><span>/</span>${tagName}`
			return
		}
		
		if (namedRouteName === 'notes') {
			// Default /notes to the first manifest entry
			let routeData = this.routes.get(route)
			
			if (!routeData && route === '/notes') {
				// Navigate to the root notes route
				const firstRoute = this.flatRoutes[0]
				if (firstRoute) {
					this.navigate(firstRoute.route, true)
					return
				}
			}
			
			if (routeData) {
				await this.namedRoutes.notes.render(routeData)
				this.updateActiveNav(route)
				this.updateBreadcrumb(route, routeData)
				this.updateTagsBar(routeData)
				document.title = `${routeData.title} - Doc.`
			} else {
				this.show404()
			}
			return
		}
		
		// Unknown route
		this.show404()
	}
	
	// Apply layout: show/hide sidebar based on named route
	applyLayout(namedRouteName) {
		const app = document.getElementById('app')
		const sidebar = document.getElementById('sidebar')
		const menuToggle = document.getElementById('menu-toggle')
		const overlay = document.getElementById('overlay')
		const breadcrumb = document.getElementById('breadcrumb')
		const tagsBar = document.getElementById('tags-bar')
		
		const namedRoute = namedRouteName ? this.namedRoutes[namedRouteName] : null
		const showSidebar = namedRoute?.sidebar ?? false
		const isTagRoute = namedRouteName === 'tags' || namedRouteName === 'tag'
		
		if (showSidebar) {
			app.classList.remove('home-page')
			sidebar.style.display = ''
			menuToggle.classList.remove('hidden')
			overlay.style.display = ''
			breadcrumb.style.display = ''
			document.getElementById('top-nav').classList.remove('no-sidebar')
		} else if (isTagRoute) {
			// Tag pages: no sidebar, but show breadcrumb
			app.classList.add('home-page')
			sidebar.style.display = 'none'
			menuToggle.classList.add('hidden')
			menuToggle.classList.remove('active')
			sidebar.classList.remove('open')
			overlay.classList.remove('active')
			overlay.style.display = 'none'
			breadcrumb.style.display = ''
			document.getElementById('top-nav').classList.add('no-sidebar')
		} else {
			app.classList.add('home-page')
			sidebar.style.display = 'none'
			menuToggle.classList.add('hidden')
			menuToggle.classList.remove('active')
			sidebar.classList.remove('open')
			overlay.classList.remove('active')
			overlay.style.display = 'none'
			breadcrumb.style.display = 'none'
			document.getElementById('top-nav').classList.add('no-sidebar')
		}
		
		// Always hide tags bar during layout reset — handleRoute will show it if needed
		tagsBar.classList.remove('visible')
		
		this.currentNamedRoute = namedRouteName
	}
	
	// Update active state in top nav
	updateTopNav(namedRouteName) {
		document.querySelectorAll('.nav-link').forEach(link => {
			const nav = link.dataset.nav
			link.classList.toggle('active', nav === namedRouteName)
		})
	}
	
	// Render home page
	renderHome() {
		const contentBody = document.getElementById('content-body')
		contentBody.innerHTML = `
			<div class="home-hero">
				<h1>Welcome Home</h1>
				<p>This is the home page of Doc.</p>
			</div>
		`
	}
	
	// Render about page
	renderAbout() {
		const contentBody = document.getElementById('content-body')
		contentBody.innerHTML = `
			<div class="home-hero">
				<h1>About</h1>
				<p>Doc. is a lightweight, file-explorer-style documentation viewer built with vanilla HTML, CSS, and JavaScript — no frameworks, no build tools.</p>
				
				<h2>Features</h2>
				<ul>
					<li><strong>SPA Routing</strong> — History API-based navigation with clean URLs</li>
					<li><strong>File Tree Sidebar</strong> — Expandable folder/file explorer for browsing notes</li>
					<li><strong>Mobile Friendly</strong> — Responsive layout with slide-out menu</li>
					<li><strong>Manifest Driven</strong> — Content structure defined in a single JSON file</li>
					<li><strong>Static Hosting</strong> — Deploys to Cloudflare Pages with zero config</li>
				</ul>
				
				<h2>Tech Stack</h2>
				<ul>
					<li>HTML5 &amp; CSS3</li>
					<li>Vanilla JavaScript (ES Modules)</li>
					<li>Cloudflare Pages</li>
				</ul>
				
				<h2>How It Works</h2>
				<p>Content is stored as plain HTML files in the <code>content-store/</code> directory. A <code>manifest.json</code> file describes the folder structure, which the app reads at startup to build the sidebar tree and register routes.</p>
				<p>When you click a link, the SPA router intercepts it, updates the URL via the History API, and fetches the corresponding HTML fragment — no full page reloads.</p>
				
			</div>
		`
	}
	
	// Render notes content
	async renderNotes(routeData) {
		const contentBody = document.getElementById('content-body')
		
		try {
			const response = await fetch(`/content-store${routeData.contentPath}`)
			if (!response.ok) throw new Error('Not found')
			const html = await response.text()

			// Sanitize: strip <style>, <script>, <iframe> and on* attributes
			const doc = new DOMParser().parseFromString(html, 'text/html')
			doc.querySelectorAll('style, script, iframe').forEach(el => el.remove())
			doc.querySelectorAll('*').forEach(el => {
				for (const attr of [...el.attributes]) {
					if (attr.name.startsWith('on')) el.removeAttribute(attr.name)
				}
			})
			contentBody.innerHTML = doc.body.innerHTML
			
			// Rewrite asset paths (images, videos, etc.)
			// Handles both relative paths and absolute /graphics/... paths
			// so they resolve against /content-store/
			const contentDir = routeData.contentPath.substring(0, routeData.contentPath.lastIndexOf('/'))
			const baseUrl = `/content-store${contentDir}/`
			contentBody.querySelectorAll('img, video, audio, source').forEach(el => {
				for (const attr of ['src', 'poster']) {
					const val = el.getAttribute(attr)
					if (!val || val.startsWith('http')) continue
					if (val.startsWith('/')) {
						// Absolute path from build — prefix with /content-store
						el.setAttribute(attr, '/content-store' + val)
					} else {
						// Relative path — resolve against content directory
						el.setAttribute(attr, baseUrl + val)
					}
				}
			})
			
			// Intercept content-area links for SPA navigation
			this.rewriteContentLinks(contentBody)

			// Render LaTeX math (once, after all DOM mutations are done)
			if (typeof renderMathInElement === 'function') {
				renderMathInElement(contentBody, {
					delimiters: [
						{ left: '\\[', right: '\\]', display: true },
						{ left: '\\(', right: '\\)', display: false }
					],
					throwOnError: false
				})
			}

			// Wire up copy-to-clipboard buttons on code blocks
			contentBody.querySelectorAll('.copy-btn').forEach(btn => {
				btn.addEventListener('click', () => {
					const code = btn.closest('.code-block').querySelector('code').textContent
					navigator.clipboard.writeText(code).then(() => {
						btn.textContent = 'Copied!'
						setTimeout(() => btn.textContent = 'Copy', 2000)
					})
				})
			})
		} catch (error) {
			contentBody.innerHTML = `<p>Error loading: ${routeData.contentPath}</p>`
		}
	}
	
	// Rewrite <a href> in parsed content so wiki-links work as SPA routes
	rewriteContentLinks(container) {
		container.querySelectorAll('a[href]').forEach(link => {
			const href = link.getAttribute('href')
			if (!href || href.startsWith('http') || href.startsWith('#') || href.startsWith('mailto:')) return
			
			// Convert content_path style hrefs to SPA routes:
			//   /readme.html         → /notes
			//   /nature/desert.html   → /notes/nature/desert
			//   /nature/README.html   → /notes/nature
			const cleaned = href
				.replace(/^\//, '')           // strip leading slash
				.replace(/\.html$/i, '')      // strip .html extension
				.replace(/\/README$/i, '')    // strip trailing /README
				.replace(/^readme$/i, '')     // root readme → empty
			
			const route = '/notes' + (cleaned ? '/' + cleaned : '')
			
			// Only rewrite if we have a matching route
			if (this.routes.has(route)) {
				link.setAttribute('href', route)
				link.setAttribute('data-link', '')
			}
		})
	}
	
	// Find a matching route (partial match)
	findMatchingRoute(route) {
		for (const [r] of this.routes) {
			if (r.startsWith(route) || route.startsWith(r)) {
				return r
			}
		}
		return null
	}
	
	// Update active state in navigation
	updateActiveNav(route) {
		document.querySelectorAll('.tree-link').forEach(link => {
			const linkRoute = link.getAttribute('href')
			link.classList.toggle('active', linkRoute === route)
		})
		
		// Expand parent folders
		const activeLink = document.querySelector(`.tree-link[href="${route}"]`)
		if (activeLink) {
			let parent = activeLink.closest('.children')
			while (parent) {
				parent.classList.add('open')
				const arrow = parent.previousElementSibling?.querySelector('.arrow')
				if (arrow) arrow.classList.add('expanded')
				parent = parent.parentElement.closest('.children')
			}
		}
	}
	
	// Update breadcrumb
	updateBreadcrumb(route, routeData) {
		const breadcrumb = document.getElementById('breadcrumb')
		const parts = route.split('/').filter(Boolean)
		
		let html = `<a href="/" data-link>Home</a>`
		let currentPath = ''
		
		parts.forEach((part, i) => {
			currentPath += '/' + part
			const isLast = i === parts.length - 1
			html += `<span>/</span>`
			if (isLast) {
				html += routeData.title
			} else {
				html += `<a href="${currentPath}" data-link>${part}</a>`
			}
		})
		
		breadcrumb.innerHTML = html
	}
	
	// Update tags bar below breadcrumb
	updateTagsBar(routeData) {
		const tagsBar = document.getElementById('tags-bar')
		const tags = routeData?.tags
		
		if (!tags || !Array.isArray(tags) || tags.length === 0) {
			tagsBar.classList.remove('visible')
			tagsBar.innerHTML = ''
			return
		}
		
		tagsBar.innerHTML = tags.map(tag => {
			const encoded = encodeURIComponent(String(tag).toLowerCase())
			return `<a class="tag-chip" href="/tags/${encoded}" data-link>#${tag}</a>`
		}).join('')
		
		tagsBar.classList.add('visible')
	}
	
	// Render tag index page (/tags)
	renderTagIndex() {
		const contentBody = document.getElementById('content-body')
		
		// Sort tags alphabetically
		const sorted = [...this.tagIndex.entries()].sort((a, b) => a[0].localeCompare(b[0]))
		
		if (sorted.length === 0) {
			contentBody.innerHTML = `
				<div class="tag-index">
					<h1>Tags</h1>
					<p>No tags found.</p>
				</div>`
			return
		}
		
		const items = sorted.map(([tag, pages]) => {
			const encoded = encodeURIComponent(tag)
			return `<li class="tag-index-item">
				<a href="/tags/${encoded}" data-link>#${tag}<span class="tag-count">${pages.length}</span></a>
			</li>`
		}).join('')
		
		contentBody.innerHTML = `
			<div class="tag-index">
				<h1>Tags</h1>
				<ul class="tag-index-list">${items}</ul>
			</div>`
	}
	
	// Render individual tag page (/tags/:tagName)
	renderTagPage(tagName) {
		const contentBody = document.getElementById('content-body')
		const key = tagName.toLowerCase()
		const pages = this.tagIndex.get(key)
		
		if (!pages || pages.length === 0) {
			contentBody.innerHTML = `
				<div class="tag-page">
					<h1>#${tagName}</h1>
					<p>No pages found with this tag. <a href="/tags" data-link>View all tags</a></p>
				</div>`
			return
		}
		
		const items = pages.map(p => {
			const icon = p.type === 'directory' ? '📁' : '📄'
			const slug = p.route.replace('/notes/', '').replace('/notes', '')
			return `<li>
				<a class="tag-page-link" href="${p.route}" data-link>
					<span class="tag-page-icon">${icon}</span>
					<span class="tag-page-title">${p.title}</span>
					<span class="tag-page-path">${slug}</span>
				</a>
			</li>`
		}).join('')
		
		contentBody.innerHTML = `
			<div class="tag-page">
				<h1>#${tagName}</h1>
				<p class="tag-page-subtitle">${pages.length} page${pages.length === 1 ? '' : 's'}</p>
				<ul class="tag-page-list">${items}</ul>
			</div>`
	}
	
	// Show 404
	show404() {
		const contentBody = document.getElementById('content-body')
		contentBody.innerHTML = `<h1>404</h1><p>Page not found. <a href="/" data-link>Go home</a></p>`
		document.getElementById('breadcrumb').innerHTML = `<a href="/" data-link>Home</a> <span>/</span> 404`
	}
}
