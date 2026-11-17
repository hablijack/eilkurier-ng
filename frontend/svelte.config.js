import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// Single-page app: the API container serves build/ and falls back to index.html.
		adapter: adapter({ fallback: 'index.html', strict: false })
	}
};
