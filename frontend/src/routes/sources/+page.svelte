<script lang="ts">
	import { onMount } from 'svelte';
	import { api, unwrap, type Catalog, type Source, type SourceIn } from '$lib/api/client';
	import { topicLook } from '$lib/reader';
	import { formatDateTime, t } from '$lib/i18n.svelte';

	let sources = $state<Source[]>([]);
	let catalog = $state<Catalog>({ topics: [], sources: [] });
	let error = $state('');
	let message = $state('');
	let form = $state<SourceIn>({
		kind: 'rss',
		name: '',
		url: '',
		category: 'Allgemein',
		fetch_fulltext: true,
		image_mode: 'auto',
		enabled: true
	});
	const imageModes = ['auto', 'page', 'feed', 'none'] as const;
	type ImageMode = (typeof imageModes)[number];

	const categories = $derived([...new Set(sources.map((s) => s.category))]);
	const catalogCategories = $derived(catalog.topics.map((c) => c.category));

	async function load() {
		try {
			[sources, catalog] = await Promise.all([unwrap(api.GET('/api/v1/sources')), unwrap(api.GET('/api/v1/catalog'))]);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function add(body: SourceIn) {
		error = '';
		message = '';
		try {
			const created = await unwrap(api.POST('/api/v1/sources', { body }));
			message = `${created.name}: ${t('sourcesPage.added')}`;
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		await add({ ...form, fetch_fulltext: form.kind === 'rss' && form.fetch_fulltext });
		form = { ...form, name: '', url: '' };
	}

	async function update(source: Source, patch: Partial<SourceIn>) {
		const { id, kind, name, url, category, fetch_fulltext, image_mode, enabled } = source;
		const body: SourceIn = {
			kind: kind as 'rss' | 'ics',
			name,
			url,
			category,
			fetch_fulltext,
			image_mode: image_mode as ImageMode,
			enabled,
			...patch
		};
		await unwrap(api.PUT('/api/v1/sources/{source_id}', { params: { path: { source_id: id } }, body }));
		await load();
	}

	async function remove(source: Source) {
		if (!confirm(`${source.name}: ${t('common.delete')}?`)) return;
		await api.DELETE('/api/v1/sources/{source_id}', { params: { path: { source_id: source.id } } });
		await load();
	}

	onMount(load);
</script>

<svelte:head><title>{t('sourcesPage.title')} · Eilkurier</title></svelte:head>

<div class="container page-head stack">
	<h1>{t('sourcesPage.title')}</h1>
	<p class="lede">{t('sourcesPage.lede')}</p>
	<p role="status" aria-live="polite">{message}</p>
	{#if error}<p class="alert error" role="alert">{t('common.error', { message: error })}</p>{/if}

	{#if sources.length === 0}<p class="muted">{t('sourcesPage.empty')}</p>{/if}
	{#each categories as category (category)}
		<section class="card" aria-labelledby="cat-{category}">
			<h2 id="cat-{category}">{topicLook(category, catalog.topics).title}</h2>
			<ul class="plain">
				{#each sources.filter((s) => s.category === category) as source (source.id)}
					<li class="row spread">
						<div class="grow">
							<strong>{source.name}</strong>
							<span class="small muted">· {t('sourcesPage.articles', { count: source.article_count ?? 0 })}</span>
							<br />
							<span class="small muted">
								{source.last_fetched_at
									? t('sourcesPage.fetched', { when: formatDateTime(source.last_fetched_at) })
									: t('sourcesPage.never')}
							</span>
							{#if source.last_error}<br /><span class="badge danger">{source.last_error}</span>{/if}
						</div>
						{#if source.kind === 'rss'}
							<div class="field image-mode">
								<label for="img-{source.id}">{t('sourcesPage.images')}</label>
								<select
									id="img-{source.id}"
									value={source.image_mode}
									onchange={(e) => update(source, { image_mode: e.currentTarget.value as ImageMode })}
								>
									{#each imageModes as mode (mode)}
										<option value={mode}>{t(`sourcesPage.images.${mode}`)}</option>
									{/each}
								</select>
							</div>
						{/if}
						<label class="check">
							<input type="checkbox" checked={source.enabled} onchange={() => update(source, { enabled: !source.enabled })} />
							{t('sourcesPage.enabled')}
						</label>
						<button class="btn danger small" type="button" onclick={() => remove(source)}
							>{t('common.delete')}<span class="visually-hidden">: {source.name}</span></button
						>
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	<form class="card stack" onsubmit={submit} aria-labelledby="add-source">
		<h2 id="add-source">{t('sourcesPage.add')}</h2>
		<div class="grid two">
			<div class="field">
				<label for="s-name">{t('sourcesPage.name')}</label>
				<input id="s-name" type="text" bind:value={form.name} required maxlength="120" />
			</div>
			<div class="field">
				<label for="s-cat">{t('sourcesPage.category')}</label>
				<input id="s-cat" type="text" bind:value={form.category} required maxlength="80" list="known-categories" />
				<datalist id="known-categories">
					{#each [...new Set([...categories, ...catalogCategories])] as c (c)}<option value={c}></option>{/each}
				</datalist>
			</div>
		</div>
		<div class="field">
			<label for="s-url">{t('sourcesPage.url')}</label>
			<input id="s-url" type="url" bind:value={form.url} required placeholder="https://" />
		</div>
		<div class="row">
			<div class="field">
				<label for="s-kind">{t('sourcesPage.kind')}</label>
				<select id="s-kind" bind:value={form.kind}>
					<option value="rss">{t('sourcesPage.kind.rss')}</option>
					<option value="ics">{t('sourcesPage.kind.ics')}</option>
				</select>
			</div>
			{#if form.kind === 'rss'}
				<div class="field">
					<label for="s-images">{t('sourcesPage.images')}</label>
					<select id="s-images" bind:value={form.image_mode}>
						{#each imageModes as mode (mode)}
							<option value={mode}>{t(`sourcesPage.images.${mode}`)}</option>
						{/each}
					</select>
				</div>
				<label class="check"><input type="checkbox" bind:checked={form.fetch_fulltext} />{t('sourcesPage.fulltext')}</label>
			{/if}
		</div>
		<button class="btn" type="submit">{t('common.add')}</button>
	</form>

	<section class="card stack" aria-labelledby="catalog">
		<h2 id="catalog">{t('sourcesPage.catalog')}</h2>
		<p class="hint">{t('sourcesPage.catalogHint')}</p>
		{#each catalogCategories as category (category)}
			<details>
				<summary><strong>{topicLook(category, catalog.topics).title}</strong> ({catalog.sources.filter((c) => c.category === category).length})</summary>
				<ul class="plain">
					{#each catalog.sources.filter((c) => c.category === category) as entry (entry.url)}
						<li class="row spread">
							<span class="grow">{entry.name}</span>
							{#if entry.source_id}
								<span class="badge ok">{t('sourcesPage.added')}</span>
							{:else}
								<button
									class="btn secondary small"
									type="button"
									onclick={() =>
										add({
											name: entry.name,
											url: entry.url,
											category: entry.category,
											kind: 'rss',
											fetch_fulltext: true,
											image_mode: entry.images,
											enabled: true
										})}
									>{t('common.add')}<span class="visually-hidden">: {entry.name}</span></button
								>
							{/if}
						</li>
					{/each}
				</ul>
			</details>
		{/each}
	</section>
</div>

<style>
	summary {
		min-height: 44px;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		cursor: pointer;
	}
</style>
