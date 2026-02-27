import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			pages: '../backend/sourcebook/static',
			assets: '../backend/sourcebook/static',
			fallback: 'index.html'
		})
	}
};

export default config;
