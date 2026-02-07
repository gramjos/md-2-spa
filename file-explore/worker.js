// Cloudflare Worker — serves static assets with SPA fallback
export default {
	async fetch(request, env) {
		const url = new URL(request.url)
		const path = url.pathname

		// Serve static assets directly (content-store, manifest, css, js, images)
		const assetResponse = await env.ASSETS.fetch(request)
		if (assetResponse.status !== 404) {
			return assetResponse
		}

		// SPA fallback — serve index.html for all unmatched routes
		const indexUrl = new URL('/index.html', request.url)
		return env.ASSETS.fetch(new Request(indexUrl, request))
	}
}
