<script lang="ts">
	import { page } from '$app/state';
	import { api, unwrap, type Edition } from '$lib/api/client';
	import type { EditionPayload, StoryItem } from '$lib/edition';
	import { t } from '$lib/i18n.svelte';

	const id = $derived(Number(page.params.id));
	let edition = $state<Edition | null>(null);
	let error = $state('');
	const paper = $derived(edition ? (edition.payload as unknown as EditionPayload) : null);

	$effect(() => {
		unwrap(api.GET('/api/v1/editions/{edition_id}', { params: { path: { edition_id: id } } }))
			.then((e) => (edition = e))
			.catch((e: Error) => (error = e.message));
	});
</script>

{#snippet story(item: StoryItem, level: 'h2' | 'h3')}
	<article class="story {item.size ?? 'medium'}">
		<header>
			<svelte:element this={level} class="headline">{item.headline}</svelte:element>
			{#if item.subhead}<p class="deck">{item.subhead}</p>{/if}
			<p class="meta">
				{item.source}{#if item.published} · {item.published}{/if}{#if item.excerpt} · {t('edition.excerpt')}{/if}
			</p>
		</header>
		{#each item.body as paragraph, i (i)}<p class:first={i === 0}>{paragraph}</p>{/each}
		{#if item.background?.length}
			<aside class="background" aria-label={t('edition.background')}>
				<p class="label">{t('edition.background')}</p>
				<ul>
					{#each item.background as event, i (i)}<li>{event}</li>{/each}
				</ul>
			</aside>
		{/if}
		{#if item.url}
			<p><a href={item.url} target="_blank" rel="noopener noreferrer">{t('edition.original')}<span class="visually-hidden">: {item.headline}</span></a></p>
		{/if}
	</article>
{/snippet}

<svelte:head><title>{paper ? `${paper.masthead.title} Nr. ${paper.edition.number}` : 'Eilkurier'}</title></svelte:head>

<div class="container page-head">
{#if error}
	<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
{:else if !paper || !edition}
	<p aria-live="polite">{t('common.loading')}</p>
{:else}
	<div class="row spread toolbar">
		<a href="/readers/{edition.reader_id}">← {t('edition.back')}</a>
		<a class="btn secondary small" href="/api/v1/editions/{edition.id}/pdf" target="_blank" rel="noopener"
			>{t('edition.downloadPdf')}</a
		>
	</div>

	<div class="newspaper" lang={paper.edition.lang}>
		<header class="paper-head">
			<p class="paper-title">{paper.masthead.title}</p>
			<p class="paper-meta">
				{t('edition.for', { reader: paper.edition.reader })} · {t('editions.number', {
					number: paper.edition.number
				})} · <time datetime={paper.edition.date}>{paper.edition.date_label}</time>
			</p>
			{#if paper.weather}
				<p class="weather">
					<strong>{t('edition.weather')} {paper.weather.place}:</strong>
					{paper.weather.summary}, {paper.weather.temp_min}° / {paper.weather.temp_max} °C · {paper.weather.wind}
				</p>
			{/if}
			<p class="sections">· {paper.sections.join(' · ')} ·</p>
		</header>

		{#if paper.lead}
			<div class="lead">{@render story(paper.lead, 'h2')}</div>
		{/if}

		<div class="columns">
			{#each paper.stories ?? [] as item, i (i)}{@render story(item, paper.lead ? 'h3' : 'h2')}{/each}

			{#if paper.briefs?.length}
				<section class="box">
					<h2>{t('edition.briefs')}</h2>
					{#each paper.briefs as brief, i (i)}
						<p><strong>{brief.headline}</strong> {brief.text} <span class="meta">({brief.source})</span></p>
					{/each}
				</section>
			{/if}
			{#if paper.calendar?.length}
				<section class="box">
					<h2>{t('edition.calendar')}</h2>
					<ul class="plain">
						{#each paper.calendar as entry, i (i)}<li><strong>{entry.when}</strong><br />{entry.what}</li>{/each}
					</ul>
				</section>
			{/if}
			{#if paper.family?.length}
				<section class="box">
					<h2>{t('edition.family')}</h2>
					{#each paper.family as letter, i (i)}
						<blockquote><p>„{letter.text}“</p><footer>— {letter.from}</footer></blockquote>
					{/each}
				</section>
			{/if}
			{#if paper.almanac}
				<section class="box">
					<h2>{t('edition.almanac')}</h2>
					<dl>
						{#each Object.entries(paper.almanac) as [key, value] (key)}<dt>{key}</dt><dd>{value}</dd>{/each}
					</dl>
				</section>
			{/if}
		</div>
	</div>
{/if}
</div>

<style>
	.toolbar {
		margin-bottom: 1rem;
	}
	.newspaper {
		font-family: var(--font-body);
		font-size: 1.0625rem;
		line-height: 1.6;
		border: 4px double var(--ink);
		padding: 1rem;
		background: var(--paper);
		hyphens: auto;
		overflow-wrap: break-word;
	}
	.paper-head {
		text-align: center;
		border-bottom: 4px double var(--ink);
		margin-bottom: 1rem;
	}
	.paper-title {
		font-family: 'Chomsky', serif;
		font-size: clamp(2.5rem, 10vw, 4.5rem);
		line-height: 1;
		margin: 0;
	}
	.paper-meta,
	.sections {
		font-family: var(--font-label);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin: 0.25rem 0;
	}
	.sections {
		background: var(--ink);
		color: var(--paper);
		padding: 0.2rem 0.5rem;
	}
	.weather {
		font-size: 0.95rem;
		margin: 0.25rem 0;
	}
	.headline {
		font-family: var(--font-label);
		text-transform: uppercase;
		text-align: center;
		hyphens: manual;
		margin: 0.5rem 0 0.25rem;
	}
	.lead .headline {
		font-size: clamp(2rem, 7vw, 3rem);
	}
	.deck {
		text-align: center;
		font-style: italic;
		font-size: 1.15em;
		margin: 0.25rem 0;
		border-top: 1px solid var(--ink);
		border-bottom: 1px solid var(--ink);
		padding: 0.25rem 0;
	}
	.meta {
		color: var(--muted);
		font-style: italic;
		font-size: 0.875rem;
		text-align: right;
		margin: 0.25rem 0 0.5rem;
	}
	.story p {
		margin: 0 0 0.75rem;
	}
	.story p.first::first-letter {
		font-family: 'Chomsky', serif;
		float: left;
		font-size: 3.2em;
		line-height: 0.85;
		padding: 0.08em 0.08em 0 0;
	}
	.story {
		break-inside: avoid-column;
		border-bottom: 1px solid var(--line);
		padding-bottom: 0.75rem;
		margin-bottom: 1rem;
	}
	.lead {
		border-bottom: 4px double var(--ink);
		margin-bottom: 1rem;
	}
	.background,
	.box {
		border: 3px double var(--ink);
		padding: 0.5rem 0.75rem;
		margin: 0.5rem 0 1rem;
		break-inside: avoid-column;
	}
	.label,
	.box h2 {
		font-family: var(--font-label);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 1.2rem;
		margin: 0 0 0.25rem;
	}
	.background ul {
		margin: 0;
		padding-left: 1.1rem;
	}
	blockquote {
		margin: 0 0 0.5rem;
		font-style: italic;
	}
	blockquote p {
		margin: 0;
	}
	dl {
		margin: 0;
	}
	dt {
		font-family: var(--font-label);
		letter-spacing: 0.05em;
	}
	dd {
		margin: 0 0 0.4rem;
	}
	@media (min-width: 48rem) {
		.newspaper {
			padding: 1.5rem 2rem;
		}
		.columns {
			column-count: 2;
			column-gap: 2rem;
			column-rule: 1px solid var(--line);
		}
		.lead :global(article) {
			column-count: 2;
			column-gap: 2rem;
		}
		.lead :global(header) {
			column-span: all;
		}
	}
	@media (min-width: 72rem) {
		.columns {
			column-count: 3;
		}
	}
</style>
