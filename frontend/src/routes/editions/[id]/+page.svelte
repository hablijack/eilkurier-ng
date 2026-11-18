<script lang="ts">
	import { page } from '$app/state';
	import { api, unwrap, type CatalogTopic, type Edition } from '$lib/api/client';
	import type { EditionPayload, StoryItem } from '$lib/edition';
	import { t } from '$lib/i18n.svelte';
	import { topicLook } from '$lib/reader';

	const id = $derived(Number(page.params.id));
	let edition = $state<Edition | null>(null);
	let error = $state('');
	let topics = $state<CatalogTopic[]>([]);
	const color = (section?: string | null) => (section ? topicLook(section, topics).color : 'grey');
	const paper = $derived(edition ? (edition.payload as unknown as EditionPayload) : null);

	$effect(() => {
		unwrap(api.GET('/api/v1/editions/{edition_id}', { params: { path: { edition_id: id } } }))
			.then((e) => (edition = e))
			.catch((e: Error) => (error = e.message));
		api.GET('/api/v1/catalog').then(({ data }) => (topics = data?.topics ?? []));
	});
</script>

{#snippet story(item: StoryItem, level: 'h2' | 'h3')}
	<article class="story {item.size ?? 'medium'} topic-{color(item.section)}">
		<header>
			{#if item.section}<p class="kicker">{item.section}</p>{/if}
			<svelte:element this={level} class="headline">{item.headline}</svelte:element>
			{#if item.subhead}<p class="deck">{item.subhead}</p>{/if}
			<p class="meta">
				{[item.source, item.published, item.excerpt ? t('edition.excerpt') : null].filter(Boolean).join(' · ')}
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
			<p class="paper-title"><img src="/rider.svg" alt="" width="72" height="43" />{paper.masthead.title}</p>
			<p class="paper-meta">
				<span>{t('edition.for', { reader: paper.edition.reader })} · {t('editions.number', {
						number: paper.edition.number
					})}</span>
				<time datetime={paper.edition.date}>{paper.edition.date_label}</time>
				{#if paper.weather}
					<span>
						<strong>{t('edition.weather')} {paper.weather.place}:</strong>
						{paper.weather.summary}, {paper.weather.temp_min}° / {paper.weather.temp_max} °C
					</span>
				{/if}
			</p>
			<ul class="sections" aria-label={t('edition.sections')}>
				{#each paper.sections as section (section)}<li class="topic-{color(section)}">{section}</li>{/each}
			</ul>
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
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		padding: 1rem;
		hyphens: auto;
		overflow-wrap: break-word;
	}
	.paper-head {
		margin-bottom: 1.25rem;
		font-family: var(--font-ui);
	}
	.paper-title {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		font-family: var(--font-display);
		font-weight: 900;
		font-size: clamp(2.4rem, 9vw, 4rem);
		line-height: 1;
		margin: 0 0 0.5rem;
	}
	.paper-title img {
		width: clamp(48px, 10vw, 80px);
		height: auto;
	}
	@media (prefers-color-scheme: dark) {
		.paper-title img {
			filter: invert(0.9);
		}
	}
	.paper-meta {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 1rem;
		font-size: 0.85rem;
		color: var(--muted);
		border-bottom: 3px solid var(--ink);
		padding-bottom: 0.4rem;
		margin: 0;
	}
	.sections {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.25rem 1.25rem;
		list-style: none;
		margin: 0;
		padding: 0.45rem 0;
		border-bottom: 1px solid var(--line);
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.sections li {
		color: var(--t);
	}
	.kicker {
		font-family: var(--font-ui);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--t);
		margin: 0 0 0.2rem;
	}
	.headline {
		font-family: var(--font-display);
		font-weight: 700;
		line-height: 1.15;
		hyphens: manual;
		margin: 0 0 0.3rem;
		font-size: 1.35rem;
	}
	.story.large .headline {
		font-size: 1.6rem;
	}
	.lead .headline {
		font-size: clamp(1.9rem, 6vw, 2.8rem);
	}
	.deck {
		font-family: var(--font-ui);
		font-size: 1.05rem;
		line-height: 1.4;
		margin: 0 0 0.3rem;
	}
	.lead .deck {
		font-size: 1.2rem;
	}
	.meta {
		font-family: var(--font-ui);
		color: var(--muted);
		font-size: 0.8rem;
		margin: 0 0 0.6rem;
	}
	.story p {
		margin: 0 0 0.75rem;
	}
	.story {
		break-inside: avoid-column;
		border-bottom: 1px solid var(--line);
		padding-bottom: 0.75rem;
		margin-bottom: 1.25rem;
	}
	.lead {
		border-bottom: 2px solid var(--ink);
		margin-bottom: 1.25rem;
	}
	.lead .story {
		border-bottom: 0;
	}
	.background {
		background: var(--band);
		border-left: 3px solid var(--brand);
		padding: 0.6rem 0.9rem;
		margin: 0.5rem 0 1rem;
		font-size: 0.95rem;
		break-inside: avoid-column;
	}
	.box {
		border-top: 3px solid var(--ink);
		padding-top: 0.4rem;
		margin: 0 0 1.5rem;
		break-inside: avoid-column;
	}
	.label,
	.box h2 {
		font-family: var(--font-ui);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 0.85rem;
		margin: 0 0 0.4rem;
	}
	.label {
		color: var(--brand);
	}
	.background ul {
		margin: 0;
		padding-left: 1.1rem;
	}
	blockquote {
		margin: 0 0 0.75rem;
		font-family: var(--font-display);
		font-style: italic;
	}
	blockquote p {
		margin: 0;
	}
	blockquote footer {
		font-family: var(--font-ui);
		font-style: normal;
		font-size: 0.85rem;
		color: var(--muted);
	}
	dl {
		margin: 0;
	}
	dt {
		font-family: var(--font-ui);
		font-weight: 700;
		font-size: 0.8rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
	}
	dd {
		margin: 0 0 0.4rem;
	}
	@media (min-width: 48rem) {
		.newspaper {
			padding: 1.5rem 2rem 2rem;
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
