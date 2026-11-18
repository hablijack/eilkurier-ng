<script lang="ts">
	import { onMount } from 'svelte';
	import { api, unwrap, type SystemStatus } from '$lib/api/client';
	import { t } from '$lib/i18n.svelte';

	let status = $state<SystemStatus | null>(null);
	let error = $state('');

	onMount(async () => {
		try {
			status = await unwrap(api.GET('/api/v1/status'));
		} catch (e) {
			error = (e as Error).message;
		}
	});
</script>

<svelte:head><title>{t('status.title')} · Eilkurier</title></svelte:head>

<div class="container narrow page-head stack">
	<h1>{t('status.title')}</h1>
	<p class="lede">{t('status.lede')}</p>
	{#if error}
		<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
	{:else if !status}
		<p aria-live="polite">{t('common.loading')}</p>
	{:else}
		{@const lm = status.language_model}
		<section class="card" aria-labelledby="services">
			<h2 id="services">{t('status.services')}</h2>
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
			</dl>
		</section>
		<section class="card" aria-labelledby="pipeline">
			<h2 id="pipeline">{t('status.pipeline')}</h2>
			<dl class="status">
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
		</section>
		<p class="small muted">Eilkurier v{status.version}</p>
	{/if}
</div>

<style>
	.status {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, auto);
		gap: 0.6rem 1rem;
		margin: 0;
	}
	.status dt {
		color: var(--muted);
	}
	.status dd {
		margin: 0;
		text-align: right;
		font-weight: 600;
	}
</style>
