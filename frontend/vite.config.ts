import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// `uv run uvicorn eilkurier.app:create_app --factory --port 8080` in another terminal
		proxy: { '/api': 'http://localhost:8080', '/health': 'http://localhost:8080' }
	}
});
