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

<section class="container intro" aria-labelledby="title">
	<h1 id="title" class="rule-title">{t('home.title')}</h1>
	<div class="intro-grid">
		<img class="newspaper" src="/img/newspaper.png" alt="" width="330" height="170" />
		<div class="intro-text">
			<p>{t('home.intro1')}</p>
			<p>{t('home.intro2')}</p>
			<p>{t('home.intro3')}</p>
		</div>
	</div>

	<!-- the old "Login" box: brown label on the left, white content on the right -->
	<div class="who-box">
		<div class="who-label">
			<h2>{t('home.whoLabel')}</h2>
			<p>{greeting}</p>
		</div>
		<div class="who-content">
			{#if loading}
				<p aria-live="polite">{t('common.loading')}</p>
			{:else if error}
				<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
			{:else}
				<ul class="readers" role="list">
					{#each readers as reader (reader.id)}
						{@const last = lastEdition(reader)}
						<li>
							<button
								class="reader-tile"
								type="button"
								onclick={() => open(reader)}
								aria-current={household.readerId === reader.id ? 'true' : undefined}
							>
								<Avatar id={reader.id} name={reader.name} size={56} />
								<span class="reader-name">{reader.name}</span>
								<span class="small muted">{deliveryText(reader)}</span>
								{#if last}
									<span class="small last">
										{t('home.lastEdition', { date: formatDate(last.issue_date) })}
									</span>
								{:else if reader.source_ids.length === 0}
									<span class="badge info">{t('home.notSetUp')}</span>
								{/if}
							</button>
						</li>
					{/each}
					<li>
						<a class="reader-tile new" href="/readers/new">
							<span class="plus"><Icon name="plus" size={26} /></span>
							<span class="reader-name">{t('home.new')}</span>
							<span class="small muted">{t('home.newHint')}</span>
						</a>
					</li>
				</ul>
			{/if}
		</div>
	</div>
</section>

<section class="band" aria-labelledby="solution">
	<div class="container">
		<h2 id="solution" class="rule-title">{t('home.solution')}</h2>
		<p class="solution-lead">{t('home.solutionLead')}</p>
		<div class="solution-grid">
			<div class="globe"><img src="/img/world.png" alt="" width="300" height="290" /></div>
			<ul class="benefits" role="list">
				<li><Icon name="clock" /><span><strong>{t('home.b1')}</strong>{t('home.b1Text')}</span></li>
				<li><Icon name="globe" /><span><strong>{t('home.b2')}</strong>{t('home.b2Text')}</span></li>
				<li><Icon name="heart" /><span><strong>{t('home.b3')}</strong>{t('home.b3Text')}</span></li>
				<li><Icon name="newspaper" /><span><strong>{t('home.b4')}</strong>{t('home.b4Text')}</span></li>
				<li><Icon name="send" /><span><strong>{t('home.b5')}</strong>{t('home.b5Text')}</span></li>
			</ul>
		</div>
	</div>
</section>

<section class="container how-section" aria-labelledby="how">
	<h2 id="how" class="rule-title">{t('home.howTitle')}</h2>
	<ol class="grid three how" role="list">
		<li class="card">
			<h3><span class="step">1</span>{t('home.how1')}</h3>
			<p class="muted">{t('home.how1Text')}</p>
		</li>
		<li class="card">
			<h3><span class="step">2</span>{t('home.how2')}</h3>
			<p class="muted">{t('home.how2Text')}</p>
		</li>
		<li class="card">
			<h3><span class="step">3</span>{t('home.how3')}</h3>
			<p class="muted">{t('home.how3Text')}</p>
		</li>
	</ol>
</section>

{#if editions.length}
	<section class="band" aria-labelledby="latest">
		<div class="container">
			<h2 id="latest" class="rule-title">{t('home.latest')}</h2>
			<div class="card">
				<EditionList {editions} {readerNames} />
			</div>
		</div>
	</section>
{/if}

<style>
	.intro {
		padding-top: 2rem;
		padding-bottom: 2.5rem;
	}
	.intro-grid {
		display: grid;
		gap: 1.5rem;
		align-items: center;
		grid-template-columns: minmax(0, 1fr);
		max-width: 60rem;
		margin: 0 auto;
	}
	@media (min-width: 48rem) {
		.intro-grid {
			grid-template-columns: 2fr 3fr;
			gap: 2.5rem;
		}
	}
	.newspaper {
		width: 100%;
		max-width: 20rem;
		height: auto;
		justify-self: center;
	}
	.intro-text {
		font-family: var(--font-body);
		text-align: justify;
		hyphens: auto;
	}
	.who-box {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		border: 2px solid var(--brand);
		max-width: 60rem;
		margin: 2.5rem auto 0;
	}
	@media (min-width: 48rem) {
		.who-box {
			grid-template-columns: 15rem minmax(0, 1fr);
		}
	}
	.who-label {
		background: var(--brand);
		color: var(--brand-ink);
		padding: 1rem 1.25rem;
	}
	.who-label h2 {
		font-family: var(--font-brand);
		font-weight: 400;
		font-size: 2.2rem;
		margin: 0 0 0.25rem;
	}
	.who-label p {
		color: var(--brand-soft);
		margin: 0;
	}
	.who-content {
		padding: 1rem;
	}
	.readers {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.75rem;
		grid-template-columns: repeat(auto-fill, minmax(10.5rem, 1fr));
	}
	.reader-tile {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.3rem;
		width: 100%;
		height: 100%;
		min-height: 10.5rem;
		padding: 1rem 0.75rem;
		text-align: center;
		font: inherit;
		color: var(--ink);
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
		cursor: pointer;
		text-decoration: none;
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.reader-tile:hover {
		border-color: var(--brand);
		box-shadow: var(--shadow-lg);
		color: var(--ink);
	}
	.reader-tile[aria-current='true'] {
		border-color: var(--brand);
	}
	.reader-name {
		font-family: var(--font-display);
		font-size: 1.15rem;
		font-weight: 700;
	}
	.last {
		color: var(--muted);
	}
	.new {
		border-style: dashed;
		border-color: var(--line-strong);
	}
	.plus {
		display: grid;
		place-items: center;
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: var(--brand-tint);
		color: var(--brand);
	}
	.solution-lead {
		text-align: center;
		font-family: var(--font-body);
		font-size: 1.15rem;
		margin: -0.5rem auto 1.75rem;
		color: var(--brand-soft);
	}
	.solution-grid {
		display: grid;
		gap: 2rem;
		align-items: center;
		grid-template-columns: minmax(0, 1fr);
		max-width: 60rem;
		margin: 0 auto;
	}
	@media (min-width: 48rem) {
		.solution-grid {
			grid-template-columns: 16rem minmax(0, 1fr);
		}
	}
	.globe {
		justify-self: center;
		background: var(--brand-ink);
		border-radius: 50%;
		padding: 1.5rem;
		width: 15rem;
		aspect-ratio: 1;
		display: grid;
		place-items: center;
	}
	.globe img {
		width: 100%;
		height: auto;
	}
	.benefits {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 1rem;
	}
	.benefits li {
		display: flex;
		gap: 0.85rem;
		align-items: flex-start;
	}
	.benefits strong {
		display: block;
		font-family: var(--font-display);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		font-size: 1.1rem;
	}
	.benefits span {
		color: var(--brand-soft);
	}
	.benefits strong {
		color: var(--brand-ink);
	}
	.how-section {
		padding-top: 2.5rem;
		padding-bottom: 2.5rem;
	}
	.how {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.how h3 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-family: var(--font-display);
		font-size: 1.15rem;
	}
	.step {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--brand);
		color: var(--brand-ink);
		font-family: var(--font-brand);
		font-size: 1rem;
	}
</style>
