<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, unwrap, type EditionSummary, type Reader, type SystemStatus } from '$lib/api/client';
	import EditionList from '$lib/components/EditionList.svelte';
	import { formatDate, t, weekdays, type MessageKey } from '$lib/i18n.svelte';

	let readers = $state<Reader[]>([]);
	let editions = $state<EditionSummary[]>([]);
	let status = $state<SystemStatus | null>(null);
	let loading = $state(true);
	let error = $state('');
	let newName = $state('');

	const readerNames = $derived(Object.fromEntries(readers.map((r) => [r.id, r.name])));

	async function load() {
		try {
			[readers, editions, status] = await Promise.all([
				unwrap(api.GET('/api/v1/readers')),
				unwrap(api.GET('/api/v1/editions', { params: { query: { limit: 10 } } })),
				unwrap(api.GET('/api/v1/status'))
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function createReader(event: SubmitEvent) {
		event.preventDefault();
		const reader = await unwrap(api.POST('/api/v1/readers', { body: { name: newName.trim() } }));
		await goto(`/readers/${reader.id}`);
	}

	function deliveryText(reader: Reader): string {
		if (!reader.active) return t('reader.inactive');
		if (reader.channel === 'none') return t('reader.noDelivery');
		const days =
			reader.delivery_days?.length === 7
				? t('days.daily')
				: (reader.delivery_days ?? []).map((d) => weekdays()[d - 1]).join(', ');
		return t('reader.delivery', {
			days,
			time: (reader.delivery_time ?? '06:00').slice(0, 5),
			channel: t(`channel.${reader.channel}` as MessageKey)
		});
	}

	function lastEdition(reader: Reader): EditionSummary | undefined {
		return editions.find((e) => e.reader_id === reader.id);
	}

	onMount(load);
</script>

<svelte:head><title>{t('nav.overview')} · Eilkurier</title></svelte:head>

<div class="stack">
	<h1>{t('overview.title')}</h1>

	{#if loading}
		<p aria-live="polite">{t('common.loading')}</p>
	{:else if error}
		<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
	{:else}
		{#if readers.length === 0}<p>{t('overview.empty')}</p>{/if}
		<ul class="grid two plain-grid" role="list">
			{#each readers as reader (reader.id)}
				{@const last = lastEdition(reader)}
				<li class="card">
					<h2><a href="/readers/{reader.id}">{reader.name}</a></h2>
					<p class="muted">{deliveryText(reader)}</p>
					<p class="small">
						{t(`theme.${reader.theme}` as MessageKey)} · {reader.interests.map((i) => i.term).join(', ')}
					</p>
					{#if last}
						<p class="small">
							<a href="/editions/{last.id}"
								>{t('reader.lastEdition', { number: last.number, date: formatDate(last.issue_date) })}</a
							>
						</p>
					{/if}
				</li>
			{/each}
		</ul>

		<form class="card row" onsubmit={createReader}>
			<div class="field grow">
				<label for="new-reader">{t('overview.newReader')}</label>
				<input id="new-reader" type="text" bind:value={newName} placeholder={t('overview.name')} required maxlength="80" />
			</div>
			<button class="btn" type="submit">{t('overview.create')}</button>
		</form>

		<section class="card" aria-labelledby="latest">
			<h2 id="latest">{t('overview.latest')}</h2>
			{#if editions.length === 0}
				<p class="muted">{t('overview.noEditions')}</p>
			{:else}
				<EditionList {editions} {readerNames} />
			{/if}
		</section>

		{#if status}
			{@const lm = status.language_model}
			<section class="card" aria-labelledby="system">
				<h2 id="system">{t('status.title')}</h2>
				<dl class="status">
					<dt>{t('status.model')}</dt>
					<dd>
						{#if !lm.configured}
							<span class="badge warn">{t('status.model.none')}</span>
						{:else if lm.available}
							<span class="badge ok">{t('status.model.available', { model: lm.model })}</span>
						{:else}
							<span class="badge warn">{t('status.model.offline')}</span>
						{/if}
					</dd>
					<dt>{t('status.telegram')}</dt>
					<dd>{status.telegram ? t('status.configured') : t('status.notConfigured')}</dd>
					<dt>{t('status.email')}</dt>
					<dd>{status.email ? t('status.configured') : t('status.notConfigured')}</dd>
					<dt>{t('status.articles')}</dt>
					<dd>{status.counts.articles_total}</dd>
					<dt>{t('status.fulltextPending')}</dt>
					<dd>{status.counts.fulltext_pending}</dd>
					<dt>{t('status.enrichmentPending')}</dt>
					<dd>{status.counts.enrichment_pending}</dd>
					<dt>{t('status.enriched')}</dt>
					<dd>{status.counts.enriched}</dd>
					<dt>{t('status.stories')}</dt>
					<dd>{status.counts.stories_open}</dd>
					<dt>{t('status.sourceErrors')}</dt>
					<dd>
						{#if status.sources_with_errors > 0}
							<a href="/sources">{status.sources_with_errors}</a>
						{:else}0{/if}
					</dd>
				</dl>
				<p class="small muted">v{status.version}</p>
			</section>
		{/if}
	{/if}
</div>

<style>
	.plain-grid {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.card h2 a {
		color: var(--ink);
	}
	.status {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, auto);
		gap: 0.4rem 1rem;
		margin: 0;
	}
	.status dd {
		margin: 0;
		text-align: right;
	}
</style>
