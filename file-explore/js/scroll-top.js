// ===== Scroll-to-Top Button =====

const SCROLL_THRESHOLD = 300

export function setupScrollToTop() {
	const scrollContainer = document.getElementById('content-display')
	const btn = document.getElementById('scroll-top')
	if (!scrollContainer || !btn) return

	scrollContainer.addEventListener('scroll', () => {
		btn.classList.toggle('visible', scrollContainer.scrollTop > SCROLL_THRESHOLD)
	}, { passive: true })

	btn.addEventListener('click', () => {
		scrollContainer.scrollTo({ top: 0, behavior: 'smooth' })
	})
}
