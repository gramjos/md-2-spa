import { Router } from './router.js'
import { buildFileTree } from './file-tree.js'
import { setupMobileMenu } from './mobile-menu.js'
import { setupThemeToggle } from './theme-toggle.js'
import { setupScrollToTop } from './scroll-top.js'

// ===== Initialize App =====
async function init() {
	const contentBody = document.getElementById('content-body')
	const fileTree = document.getElementById('file-tree')

	// --- Phase 1: Immediate UI (no manifest needed) ---
	const router = new Router()

	setupThemeToggle()
	setupMobileMenu()
	setupScrollToTop()

	// Lightbox close handlers
	const lightbox = document.getElementById('media-lightbox')
	const closeLightbox = () => {
		lightbox.classList.remove('active')
		document.body.style.overflow = ''
	}
	document.getElementById('lightbox-close').addEventListener('click', closeLightbox)
	lightbox.addEventListener('click', (e) => {
		if (e.target === lightbox) closeLightbox()
	})
	document.addEventListener('keydown', (e) => {
		if (e.key === 'Escape' && lightbox.classList.contains('active')) closeLightbox()
	})

	// Intercept all internal link clicks (using data-link attribute)
	document.addEventListener('click', (e) => {
		const link = e.target.closest('a[data-link]')
		if (link) {
			e.preventDefault()
			const href = link.getAttribute('href')
			
			// Same-page heading anchor: scroll without re-rendering
			if (href.startsWith('#')) {
				const target = document.getElementById(decodeURIComponent(href.slice(1)))
				if (target) {
					history.pushState(null, '', href)
					target.scrollIntoView({ behavior: 'smooth' })
				}
				return
			}
			
			router.navigate(href)
		}
	})

	// Handle folder toggle clicks (delegated — works after tree populates)
	fileTree.addEventListener('click', (e) => {
		const link = e.target.closest('.tree-link')
		if (!link) return

		const hasChildren = link.dataset.hasChildren === 'true'
		if (hasChildren) {
			const arrow = link.querySelector('.arrow')
			const children = link.nextElementSibling

			if (children) {
				children.classList.toggle('open')
				arrow.classList.toggle('expanded')
			}
		}
	})

	// Render the initial route immediately.
	// Home and About render inline HTML — no manifest needed.
	// Notes/Tags routes will await router.whenReady inside handleRoute().
	router.handleRoute()

	// --- Phase 2: Deferred manifest load (background) ---
	try {
		const response = await fetch('/manifest.json')
		if (!response.ok) throw new Error(`Failed to load manifest: ${response.status}`)
		const manifest = await response.json()

		router.manifest = manifest
		router.buildRoutes(manifest)

		fileTree.innerHTML = buildFileTree(manifest, router)

		// Manifest is ready — unblock any pending notes/tags renders
		router.markReady()
	} catch (error) {
		console.error('App init failed:', error)
		router.markReady() // unblock to avoid hanging deep-link navigations
		contentBody.innerHTML = `
			<div class="home-hero">
				<h1>Failed to load</h1>
				<p>${error.message}</p>
				<p>Make sure you're serving this app with a local server (e.g. <code>npx serve</code>), not opening the HTML file directly.</p>
			</div>
		`
	}
}

init()
