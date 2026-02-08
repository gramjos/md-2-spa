// ===== Sidebar Resize =====
// Allows horizontal resizing of the sidebar by dragging a vertical handle.
// Persists width to localStorage.

export function initSidebarResize() {
	const resizer = document.getElementById('sidebar-resizer')
	const sidebar = document.getElementById('sidebar')
	const root = document.documentElement

	if (!resizer || !sidebar) return

	const MIN_WIDTH = 180
	const MAX_WIDTH = 500
	const STORAGE_KEY = 'sidebar-width'

	// Restore saved width
	const saved = localStorage.getItem(STORAGE_KEY)
	if (saved) {
		const w = parseInt(saved, 10)
		if (w >= MIN_WIDTH && w <= MAX_WIDTH) {
			root.style.setProperty('--sidebar-width', w + 'px')
		}
	}

	let isDragging = false

	function onPointerDown(e) {
		// Only respond to left mouse button or touch
		if (e.button && e.button !== 0) return

		isDragging = true
		document.body.classList.add('sidebar-resizing')
		resizer.classList.add('active')

		document.addEventListener('pointermove', onPointerMove)
		document.addEventListener('pointerup', onPointerUp)
		resizer.setPointerCapture(e.pointerId)

		e.preventDefault()
	}

	function onPointerMove(e) {
		if (!isDragging) return

		const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX))
		root.style.setProperty('--sidebar-width', newWidth + 'px')
	}

	function onPointerUp(e) {
		if (!isDragging) return

		isDragging = false
		document.body.classList.remove('sidebar-resizing')
		resizer.classList.remove('active')

		document.removeEventListener('pointermove', onPointerMove)
		document.removeEventListener('pointerup', onPointerUp)

		// Persist
		const width = parseInt(getComputedStyle(root).getPropertyValue('--sidebar-width'), 10)
		if (width) localStorage.setItem(STORAGE_KEY, width)
	}

	resizer.addEventListener('pointerdown', onPointerDown)
}
