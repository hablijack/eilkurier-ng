<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, unwrap, type EditionSummary, type Reader } from '$lib/api/client';
	import Avatar from '$lib/components/Avatar.svelte';
	import EditionList from '$lib/components/EditionList.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { chooseReader, household } from '$lib/household.svelte';
	import { formatDate, t } from '$lib/i18n.svelte';
	import { deliveryText } from '$lib/reader';

	let readers = $state<Reader[]>([]);
	let editions = $state<EditionSummary[]>([]);
	let loading = $state(true);
	let error = $state('');

	const readerNames = $derived(Object.fromEntries(readers.map((r) => [r.id, r.name])));

	const greeting = $derived.by(() => {
		const hour = new Date().getHours();
		return t(hour < 11 ? 'home.morning' : hour < 18 ? 'home.day' : 'home.evening');
	});

	async function load() {
		try {
			[readers, editions] = await Promise.all([
				unwrap(api.GET('/api/v1/readers')),
				unwrap(api.GET('/api/v1/editions', { params: { query: { limit: 10 } } }))
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function open(reader: Reader) {
		chooseReader(reader.id);
		await goto(reader.source_ids.length ? `/readers/${reader.id}` : `/readers/${reader.id}/setup`);
	}

	function lastEdition(reader: Reader): EditionSummary | undefined {
		return editions.find((e) => e.reader_id === reader.id);
	}

	onMount(load);
</script>

<svelte:head><title>Eilkurier</title></svelte:head>

<section class="hero">
	<div class="container">
		<h1>{greeting}</h1>
		<p class="lede">{t('home.who')}</p>

		{#if loading}
			<p aria-live="polite">{t('common.loading')}</p>
		{:else if error}
			<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
		{:else}
			<ul class="grid tiles readers" role="list">
				{#each readers as reader (reader.id)}
					{@const last = lastEdition(reader)}
					<li>
						<button
							class="reader-tile"
							type="button"
							onclick={() => open(reader)}
							aria-current={household.readerId === reader.id ? 'true' : undefined}
						>
							<Avatar id={reader.id} name={reader.name} size={64} />
							<span class="reader-name">{reader.name}</span>
							<span class="small muted">{deliveryText(reader)}</span>
							{#if last}
								<span class="small last">
									{t('home.lastEdition', { date: formatDate(last.issue_date) })}
									{#if last.lead_headline}<br /><em>{last.lead_headline}</em>{/if}
								</span>
							{:else if reader.source_ids.length === 0}
								<span class="badge info">{t('home.notSetUp')}</span>
							{/if}
						</button>
					</li>
				{/each}
				<li>
					<a class="reader-tile new" href="/readers/new">
						<span class="plus"><Icon name="plus" size={28} /></span>
						<span class="reader-name">{t('home.new')}</span>
						<span class="small muted">{t('home.newHint')}</span>
					</a>
				</li>
			</ul>
		{/if}
	</div>
</section>

<section class="band" aria-labelledby="how">
	<div class="container">
		<h2 id="how">{t('home.howTitle')}</h2>
		<ol class="grid three how" role="list">
			<li class="card">
				<span class="how-icon topic-blue"><Icon name="heart" /></span>
				<h3>{t('home.how1')}</h3>
				<p class="muted">{t('home.how1Text')}</p>
			</li>
			<li class="card">
				<span class="how-icon topic-violet"><Icon name="pencil" /></span>
				<h3>{t('home.how2')}</h3>
				<p class="muted">{t('home.how2Text')}</p>
			</li>
			<li class="card">
				<span class="how-icon topic-green"><Icon name="send" /></span>
				<h3>{t('home.how3')}</h3>
				<p class="muted">{t('home.how3Text')}</p>
			</li>
		</ol>
	</div>
</section>

{#if editions.length}
	<section class="container latest" aria-labelledby="latest">
		<h2 id="latest">{t('home.latest')}</h2>
		<div class="card">
			<EditionList {editions} {readerNames} />
		</div>
	</section>
{/if}

<style>
	.hero {
		padding: 2.25rem 0 2.5rem;
	}
	.lede {
		color: var(--muted);
		font-size: 1.15rem;
		margin-bottom: 1.5rem;
	}
	.readers {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.reader-tile {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		width: 100%;
		height: 100%;
		min-height: 12rem;
		padding: 1.25rem 1rem;
		text-align: center;
		font: inherit;
		color: var(--ink);
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		cursor: pointer;
		text-decoration: none;
		transition:
			box-shadow 0.15s,
			border-color 0.15s,
			transform 0.15s;
	}
	.reader-tile:hover {
		border-color: var(--brand);
		box-shadow: var(--shadow-lg);
		transform: translateY(-2px);
		color: var(--ink);
	}
	.reader-tile[aria-current='true'] {
		border-color: var(--brand);
		border-width: 2px;
	}
	.reader-name {
		font-size: 1.2rem;
		font-weight: 700;
	}
	.last {
		color: var(--muted);
	}
	.new {
		border-style: dashed;
		background: transparent;
		box-shadow: none;
	}
	.plus {
		display: grid;
		place-items: center;
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: var(--brand-tint);
		color: var(--brand);
	}
	.how {
		list-style: none;
		margin: 1rem 0 0;
		padding: 0;
	}
	.how-icon {
		display: inline-grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 12px;
		background: var(--t-tint);
		color: var(--t);
		margin-bottom: 0.75rem;
	}
	.latest {
		padding-top: 2rem;
	}
</style>
