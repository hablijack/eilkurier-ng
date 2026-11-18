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
		{ href: '/sources', key: 'nav.sources' as const, icon: 'rss' as const },
		{ href: '/system', key: 'nav.system' as const, icon: 'activity' as const }
	]);

	function current(href: string): boolean {
		return page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);
	}
</script>

<a class="skip-link" href="#main">{t('app.skip')}</a>

<header class="site-header">
	<div class="container header-inner">
		<a class="brand" href="/">
			<img src="/rider.svg" alt="" width="64" height="38" />
			<span class="brand-text">
				<span class="wordmark">Eilkurier</span>
				<span class="slogan">{t('app.slogan')}</span>
			</span>
		</a>
		{#if session?.authenticated}
			<nav aria-label={t('nav.main')}>
				<ul>
					{#each links as link (link.href)}
						<li>
							<a href={link.href} aria-current={current(link.href) ? 'page' : undefined}>
								<Icon name={link.icon} size={18} />{t(link.key)}
							</a>
						</li>
					{/each}
				</ul>
				<a class="who" href="/" aria-label={reader ? t('nav.switchReader', { name: reader.name }) : t('nav.chooseReader')}>
					{#if reader}
						<Avatar id={reader.id} name={reader.name} size={36} />
						<span class="who-name">{reader.name}</span>
					{:else}
						<Icon name="users" />
						<span class="who-name">{t('nav.chooseReader')}</span>
					{/if}
				</a>
			</nav>
		{/if}
	</div>
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
		<div>
			<p class="footer-brand">Eilkurier</p>
			<p class="small muted">{t('footer.about')}</p>
		</div>
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
</footer>

<style>
	.site-header {
		background: var(--bg);
		border-bottom: 1px solid var(--line);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.header-inner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.25rem 1.5rem;
		padding-top: 0.6rem;
		padding-bottom: 0.6rem;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.75rem;
		color: var(--brand);
		text-decoration: none;
		min-height: 44px;
	}
	.brand img {
		width: 56px;
		height: auto;
	}
	@media (prefers-color-scheme: dark) {
		.brand img {
			filter: invert(0.8) sepia(0.6) saturate(2) hue-rotate(-20deg);
		}
	}
	.brand-text {
		display: flex;
		flex-direction: column;
		line-height: 1.05;
	}
	.wordmark {
		font-family: var(--font-display);
		font-weight: 800;
		font-size: 1.7rem;
		letter-spacing: -0.01em;
		color: var(--ink);
	}
	.slogan {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--brand);
	}
	nav {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	nav ul {
		display: flex;
		gap: 0.15rem;
		list-style: none;
		margin: 0;
		padding: 0;
		overflow-x: auto;
	}
	nav ul a {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 44px;
		padding: 0 0.75rem;
		border-radius: 999px;
		color: var(--ink);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}
	nav ul a:hover {
		background: var(--band);
	}
	nav ul a[aria-current='page'] {
		background: var(--brand-tint);
		color: var(--brand);
	}
	.who {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		padding: 0.2rem 0.8rem 0.2rem 0.25rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		color: var(--ink);
		text-decoration: none;
		font-weight: 600;
	}
	.who:hover {
		background: var(--band);
		color: var(--ink);
	}
	@media (max-width: 40rem) {
		nav {
			width: 100%;
			flex-wrap: nowrap;
			justify-content: space-between;
		}
		nav ul {
			flex: 1;
			min-width: 0;
		}
		nav ul a {
			padding: 0 0.6rem;
		}
		.who-name {
			display: none;
		}
		.who {
			padding: 0.2rem;
		}
		.slogan {
			display: none;
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
	.site-footer {
		background: var(--band);
		border-top: 1px solid var(--line);
		padding: 2rem 0;
	}
	.footer-inner {
		display: grid;
		gap: 1.5rem;
		grid-template-columns: minmax(0, 1fr);
	}
	@media (min-width: 48rem) {
		.footer-inner {
			grid-template-columns: 2fr 1fr 1fr;
		}
	}
	.footer-brand {
		font-family: var(--font-display);
		font-weight: 800;
		font-size: 1.25rem;
		margin: 0 0 0.25rem;
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
		color: var(--ink);
	}
	.footer-tools {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		align-items: flex-start;
	}
	.footer-tools label {
		font-weight: 600;
		font-size: 0.9rem;
	}
	.footer-tools select {
		width: auto;
	}
</style>
