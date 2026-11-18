<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, unwrap, type Reader } from '$lib/api/client';
	import Avatar from '$lib/components/Avatar.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { chooseReader, household } from '$lib/household.svelte';
	import { i18n, languages, setLang, t, type Lang } from '$lib/i18n.svelte';

	let { children } = $props();

	let session = $state<{ pin_required: boolean; authenticated: boolean } | null>(null);
	let pin = $state('');
	let pinError = $state('');
	let reader = $state<Reader | null>(null);

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

	// The reader chosen on this device; forget it when it no longer exists.
	$effect(() => {
		const id = household.readerId;
		const ready = session?.authenticated;
		void page.url.pathname; // refresh the name after edits
		if (!id || !ready) {
			reader = null;
			return;
		}
		api.GET('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } } }).then(({ data, response }) => {
			if (response.status === 404) chooseReader(null);
			reader = data ?? null;
		});
	});

	onMount(() => {
		document.documentElement.lang = i18n.lang;
		loadSession();
		const onUnauthorized = () => loadSession();
		window.addEventListener('eilkurier:unauthorized', onUnauthorized);
		return () => window.removeEventListener('eilkurier:unauthorized', onUnauthorized);
	});

	const links = $derived([
		...(reader ? [{ href: `/readers/${reader.id}`, key: 'nav.mine' as const, icon: 'newspaper' as const }] : []),
		{ href: '/letters', key: 'nav.letters' as const, icon: 'message' as const },
		{ href: '/sources', key: 'nav.sources' as const, icon: 'rss' as const }
		// "System" is in the footer: the header keeps room for the centred logo.
	]);

	function current(href: string): boolean {
		return page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);
	}
</script>

<a class="skip-link" href="#main">{t('app.skip')}</a>

<header class="site-header">
	<div class="bar">
		<div class="container header-inner">
			{#if session?.authenticated}
				<nav aria-label={t('nav.main')}>
					<ul>
						{#each links as link (link.href)}
							<li>
								<a href={link.href} aria-current={current(link.href) ? 'page' : undefined}>
									<Icon name={link.icon} size={16} />{t(link.key)}
								</a>
							</li>
						{/each}
					</ul>
				</nav>
			{/if}
			<a class="brand" href="/">
				<img src="/logo-white.svg" alt="" width="64" height="37" />
				<span class="wordmark">Eilkurier</span>
			</a>
			{#if session?.authenticated}
				<a
					class="who"
					href="/"
					aria-label={reader ? t('nav.switchReader', { name: reader.name }) : t('nav.chooseReader')}
				>
					{#if reader}
						<Avatar id={reader.id} name={reader.name} size={34} />
						<span class="who-name">{reader.name}</span>
					{:else}
						<Icon name="users" />
						<span class="who-name">{t('nav.chooseReader')}</span>
					{/if}
				</a>
			{/if}
		</div>
	</div>
	<p class="slogan">{t('app.slogan')}</p>
</header>

<main id="main" tabindex="-1">
	{#if session === null}
		<p class="container page-head" aria-live="polite">{t('common.loading')}</p>
	{:else if !session.authenticated}
		<div class="container narrow page-head">
			<form class="card pin stack" onsubmit={login}>
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
		</div>
	{:else}
		{@render children()}
	{/if}
</main>

<footer class="site-footer">
	<div class="container footer-inner">
		<div class="footer-brand">
			<p class="footer-title">Eilkurier</p>
			<p class="small">{t('footer.about')}</p>
			<p class="small">&copy; 2018–{new Date().getFullYear()}</p>
		</div>
		<div class="footer-rider">
			<img src="/logo-white.svg" alt="" width="110" height="63" />
			<p class="footer-slogan">{t('app.slogan')}</p>
		</div>
		<div class="footer-side">
			<ul class="footer-links" aria-label={t('footer.links')}>
				<li><a href="/letters">{t('nav.letters')}</a></li>
				<li><a href="/sources">{t('nav.sources')}</a></li>
				<li><a href="/system">{t('nav.system')}</a></li>
				<li><a href="/api/v1/docs">{t('footer.api')}</a></li>
			</ul>
			<div class="footer-tools">
				<label for="lang">{t('nav.language')}</label>
				<select id="lang" value={i18n.lang} onchange={(e) => setLang(e.currentTarget.value as Lang)}>
					{#each languages as lang (lang)}
						<option value={lang}>{lang === 'de' ? 'Deutsch' : 'English'}</option>
					{/each}
				</select>
				{#if session?.pin_required && session.authenticated}
					<button class="btn secondary small" type="button" onclick={logout}>{t('nav.logout')}</button>
				{/if}
			</div>
		</div>
	</div>
</footer>

<style>
	/* The classic Eilkurier header: brown bar (navigation left, white rider in the middle), then a white
	   banner with the slogan in brown, closed by a brown rule. */
	.site-header {
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.bar {
		background: var(--brand);
		color: var(--brand-ink);
	}
	.header-inner {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: center;
		gap: 0.5rem 1rem;
		min-height: 4.5rem;
	}
	.brand {
		grid-column: 2;
		grid-row: 1;
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--brand-ink);
		text-decoration: none;
		min-height: 44px;
	}
	.brand:hover {
		color: var(--brand-ink);
	}
	.brand img {
		width: 62px;
		height: auto;
	}
	.wordmark {
		font-family: var(--font-brand);
		font-weight: 700;
		font-size: 1.9rem;
		line-height: 1;
	}
	nav {
		grid-column: 1;
		grid-row: 1;
		min-width: 0;
	}
	nav ul {
		display: flex;
		gap: 0.25rem;
		list-style: none;
		margin: 0;
		padding: 0;
		overflow-x: auto;
		scrollbar-width: none;
	}
	nav a {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 44px;
		padding: 0 0.7rem;
		color: var(--brand-ink);
		font-size: 0.85rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		text-decoration: none;
		white-space: nowrap;
		border-bottom: 2px solid transparent;
	}
	nav a:hover {
		color: var(--brand-ink);
		border-bottom-color: var(--brand-soft);
	}
	nav a[aria-current='page'] {
		border-bottom-color: var(--brand-ink);
	}
	.bar :focus-visible {
		outline-color: var(--brand-ink);
	}
	.who {
		grid-column: 3;
		grid-row: 1;
		justify-self: end;
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		padding: 0.2rem 0.85rem 0.2rem 0.25rem;
		border: 2px solid var(--brand-soft);
		border-radius: 999px;
		color: var(--brand-ink);
		text-decoration: none;
		font-weight: 700;
	}
	.who:hover {
		color: var(--brand-ink);
		border-color: var(--brand-ink);
	}
	.who :global(.avatar) {
		background: var(--brand-ink);
		color: var(--brand);
	}
	.slogan {
		margin: 0;
		background: var(--bg);
		border-bottom: 2px solid var(--brand);
		color: var(--brand);
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 0.9rem;
		letter-spacing: 0.04em;
		line-height: 2;
		text-align: center;
		text-transform: uppercase;
	}
	@media (max-width: 48rem) {
		.header-inner {
			grid-template-columns: minmax(0, 1fr) auto;
			min-height: 0;
			padding-top: 0.4rem;
		}
		.brand {
			grid-column: 1;
		}
		.who {
			grid-column: 2;
		}
		nav {
			grid-column: 1 / -1;
			grid-row: 2;
			margin: 0 -1rem;
			padding: 0 0.5rem;
		}
		.who-name {
			display: none;
		}
		.who {
			padding: 0.2rem;
		}
	}
	main {
		min-height: 60vh;
		padding-bottom: 3rem;
	}
	main:focus {
		outline: none;
	}
	.pin {
		max-width: 24rem;
		margin: 2rem auto;
	}

	/* Footer: brown, the wordmark between rules, the white rider and the slogan. */
	.site-footer {
		background: var(--brand);
		color: var(--brand-ink);
		padding: 2rem 0 1.5rem;
	}
	.site-footer a {
		color: var(--brand-ink);
	}
	.site-footer :focus-visible {
		outline-color: var(--brand-ink);
	}
	.footer-inner {
		display: grid;
		gap: 1.75rem;
		grid-template-columns: minmax(0, 1fr);
		align-items: start;
	}
	@media (min-width: 48rem) {
		.footer-inner {
			grid-template-columns: 1fr auto 1fr;
		}
		.footer-side {
			justify-self: end;
		}
	}
	.footer-title {
		font-family: var(--font-brand);
		font-weight: 700;
		font-size: 1.6rem;
		text-transform: uppercase;
		width: fit-content;
		margin: 0 0 0.5rem;
	}
	.footer-title::before,
	.footer-title::after {
		content: '';
		display: block;
	}
	.footer-title::before {
		width: 100%;
		height: 0.4rem;
		border-top: 2px solid currentColor;
	}
	.footer-title::after {
		width: 55%;
		height: 0.5rem;
		border-bottom: 2px solid currentColor;
	}
	.footer-brand .small {
		color: var(--brand-soft);
		max-width: 22rem;
	}
	.footer-rider {
		text-align: center;
	}
	.footer-rider img {
		width: 110px;
		height: auto;
	}
	.footer-slogan {
		font-family: var(--font-display);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin: 0.5rem 0 0;
	}
	.footer-side {
		display: flex;
		gap: 2rem;
		flex-wrap: wrap;
	}
	.footer-links {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.footer-links a {
		display: inline-flex;
		min-height: 36px;
		align-items: center;
	}
	.footer-tools {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		align-items: flex-start;
	}
	.footer-tools label {
		font-weight: 700;
		font-size: 0.9rem;
	}
	.footer-tools select {
		width: auto;
	}
</style>
