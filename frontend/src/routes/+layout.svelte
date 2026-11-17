<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, unwrap } from '$lib/api/client';
	import { i18n, languages, setLang, t, type Lang } from '$lib/i18n.svelte';

	let { children } = $props();

	let session = $state<{ pin_required: boolean; authenticated: boolean } | null>(null);
	let pin = $state('');
	let pinError = $state('');

	async function loadSession() {
		session = await unwrap(api.GET('/api/v1/session'));
	}

	async function login(event: SubmitEvent) {
		event.preventDefault();
		pinError = '';
		try {
			session = await unwrap(api.POST('/api/v1/session', { body: { pin } }));
			pin = '';
		} catch {
			pinError = t('pin.wrong');
		}
	}

	async function logout() {
		await api.DELETE('/api/v1/session');
		await loadSession();
	}

	onMount(() => {
		document.documentElement.lang = i18n.lang;
		loadSession();
		const onUnauthorized = () => loadSession();
		window.addEventListener('eilkurier:unauthorized', onUnauthorized);
		return () => window.removeEventListener('eilkurier:unauthorized', onUnauthorized);
	});

	const links = [
		{ href: '/', key: 'nav.overview' },
		{ href: '/sources', key: 'nav.sources' },
		{ href: '/letters', key: 'nav.letters' }
	] as const;

	function current(href: string): boolean {
		return href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
	}
</script>

<a class="skip-link" href="#main">{t('app.skip')}</a>

<header class="masthead">
	<div class="container masthead-inner">
		<a class="brand" href="/" aria-label="Eilkurier – {t('nav.overview')}">
			<img src="/rider.svg" alt="" width="56" height="34" />
			<span class="title">Eilkurier</span>
		</a>
		<p class="slogan">{t('app.slogan')}</p>
	</div>
	{#if session?.authenticated}
		<nav class="container" aria-label={t('nav.main')}>
			<ul>
				{#each links as link (link.href)}
					<li>
						<a href={link.href} aria-current={current(link.href) ? 'page' : undefined}>{t(link.key)}</a>
					</li>
				{/each}
			</ul>
			<div class="tools">
				<label class="visually-hidden" for="lang">{t('nav.language')}</label>
				<select id="lang" value={i18n.lang} onchange={(e) => setLang(e.currentTarget.value as Lang)}>
					{#each languages as lang (lang)}
						<option value={lang}>{lang.toUpperCase()}</option>
					{/each}
				</select>
				{#if session.pin_required}
					<button class="btn secondary small" type="button" onclick={logout}>{t('nav.logout')}</button>
				{/if}
			</div>
		</nav>
	{/if}
</header>

<main id="main" class="container" tabindex="-1">
	{#if session === null}
		<p aria-live="polite">{t('common.loading')}</p>
	{:else if !session.authenticated}
		<form class="card double pin stack" onsubmit={login}>
			<h1>{t('pin.title')}</h1>
			<div class="field">
				<label for="pin">{t('pin.label')}</label>
				<input
					id="pin"
					type="password"
					inputmode="numeric"
					autocomplete="current-password"
					bind:value={pin}
					aria-describedby={pinError ? 'pin-error' : undefined}
					aria-invalid={pinError ? 'true' : undefined}
					required
				/>
			</div>
			{#if pinError}<p id="pin-error" class="alert error" role="alert">{pinError}</p>{/if}
			<button class="btn" type="submit">{t('pin.submit')}</button>
		</form>
	{:else}
		{@render children()}
	{/if}
</main>

<style>
	.masthead {
		border-bottom: 4px double var(--ink);
		margin-bottom: 1.5rem;
		padding-top: 0.75rem;
	}
	.masthead-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--ink);
		text-decoration: none;
	}
	@media (prefers-color-scheme: dark) {
		.brand img {
			filter: invert(0.92);
		}
	}
	.title {
		font-family: 'Chomsky', serif;
		font-size: clamp(2.4rem, 9vw, 3.6rem);
		line-height: 1;
	}
	.slogan {
		font-family: var(--font-label);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		margin: 0.2rem 0 0.6rem;
	}
	nav {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		border-top: 1px solid var(--ink);
		padding-top: 0.25rem;
		padding-bottom: 0.25rem;
	}
	nav ul {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	nav a {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 0.75rem;
		font-family: var(--font-label);
		font-size: 1.25rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--ink);
		text-decoration: none;
		border-radius: 6px;
	}
	nav a[aria-current='page'] {
		background: var(--ink);
		color: var(--paper);
	}
	.tools {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.tools select {
		width: auto;
	}
	main {
		padding-bottom: 3rem;
	}
	main:focus {
		outline: none;
	}
	.pin {
		max-width: 24rem;
		margin: 2rem auto;
	}
</style>
