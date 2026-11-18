<script lang="ts">
	import { tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		api,
		unwrap,
		type Catalog,
		type CatalogEntry,
		type Reader,
		type ReaderIn,
		type Source,
		type SystemStatus
	} from '$lib/api/client';
	import DeliveryFields from '$lib/components/DeliveryFields.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RankList, { type RankItem } from '$lib/components/RankList.svelte';
	import SourceCard from '$lib/components/SourceCard.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import StyleFields from '$lib/components/StyleFields.svelte';
	import TopicCard from '$lib/components/TopicCard.svelte';
	import { chooseReader } from '$lib/household.svelte';
	import { t, type MessageKey } from '$lib/i18n.svelte';
	import { topicLook } from '$lib/reader';

	/** A newspaper the reader can pick: a catalog entry or one of the household's own sources. */
	type Pick = { url: string; name: string; description: string; category: string; sourceId: number | null };

	const id = $derived(Number(page.params.id));
	const stepKeys = ['wizard.step.topics', 'wizard.step.sources', 'wizard.step.order', 'wizard.step.delivery'] as const;

	let catalog = $state<Catalog | null>(null);
	let reader = $state<Reader | null>(null);
	let status = $state<SystemStatus | null>(null);
	let form = $state<ReaderIn | null>(null);
	let picks = $state<Record<string, Pick>>({});
	let topics = $state<string[]>([]); // chosen topic categories, in the order they were chosen
	let selected = $state<string[]>([]); // urls
	let ranked = $state<RankItem[]>([]);
	let step = $state(0);
	let filter = $state<Record<string, string>>({});
	let error = $state('');
	let busy = $state(false);
	let heading = $state<HTMLHeadingElement | null>(null);

	const topicList = $derived(catalog?.topics ?? []);
	const ownSources = $derived(Object.values(picks).filter((p) => !catalog?.sources.some((e) => e.url === p.url)));

	function entriesOf(category: string): CatalogEntry[] {
		return catalog?.sources.filter((e) => e.category === category) ?? [];
	}

	function groupsOf(category: string): [string, CatalogEntry[]][] {
		const query = (filter[category] ?? '').trim().toLowerCase();
		const groups = new Map<string, CatalogEntry[]>();
		for (const entry of entriesOf(category)) {
			if (query && !`${entry.name} ${entry.description}`.toLowerCase().includes(query)) continue;
			const group = entry.group ?? '';
			groups.set(group, [...(groups.get(group) ?? []), entry]);
		}
		return [...groups];
	}

	async function load() {
		try {
			const [c, r, s, st] = await Promise.all([
				unwrap(api.GET('/api/v1/catalog')),
				unwrap(api.GET('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } } })),
				unwrap(api.GET('/api/v1/sources')),
				unwrap(api.GET('/api/v1/status'))
			]);
			catalog = c;
			status = st;
			setReader(r);
			chooseReader(r.id);
			const known: Record<string, Pick> = {};
			for (const e of c.sources) known[e.url] = { ...e, sourceId: e.source_id ?? null };
			const mine = r.source_ids.map((sid) => s.find((x) => x.id === sid)).filter((x): x is Source => !!x);
			for (const src of mine) {
				known[src.url] ??= { url: src.url, name: src.name, description: src.category, category: src.category, sourceId: src.id };
			}
			picks = known;
			selected = mine.map((x) => x.url);
			topics = [...new Set(mine.map((x) => x.category))].filter((cat) => c.topics.some((tp) => tp.category === cat));
			ranked = selected.map(item);
			const wanted = Number(page.url.searchParams.get('step'));
			if (wanted >= 1 && wanted <= 4) step = wanted - 1;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function setReader(r: Reader) {
		reader = r;
		const { id: _id, telegram_linked, telegram_link_code, interests, source_ids, ...rest } = r;
		form = { ...rest, delivery_time: (rest.delivery_time ?? '06:00').slice(0, 5) };
	}

	function item(url: string): RankItem {
		const p = picks[url];
		const look = topicLook(p.category, topicList);
		return { key: url, name: p.name, detail: look.title, color: look.color };
	}

	function toggleTopic(category: string) {
		if (topics.includes(category)) {
			topics = topics.filter((c) => c !== category);
			selected = selected.filter((url) => picks[url]?.category !== category);
			return;
		}
		topics = [...topics, category];
		if (!selected.some((url) => picks[url]?.category === category)) {
			selected = [...selected, ...entriesOf(category).filter((e) => e.recommended).map((e) => e.url)];
		}
	}

	function toggleSource(url: string) {
		selected = selected.includes(url) ? selected.filter((u) => u !== url) : [...selected, url];
	}

	/** Keep the order the reader already chose; new picks follow, by topic rank. */
	function rebuildRanking() {
		const kept = ranked.map((r) => r.key).filter((url) => selected.includes(url));
		const rank = (url: string) => {
			const i = topics.indexOf(picks[url].category);
			return i < 0 ? topics.length : i;
		};
		const added = selected.filter((url) => !kept.includes(url)).sort((a, b) => rank(a) - rank(b));
		ranked = [...kept, ...added].map(item);
	}

	const canContinue = $derived(step === 0 ? topics.length > 0 || ownSources.length > 0 : step === 1 ? selected.length > 0 : true);

	async function go(to: number) {
		if (to === 2) rebuildRanking();
		step = to;
		await tick();
		window.scrollTo({ top: 0 });
		heading?.focus();
	}

	async function finish() {
		if (!form || !reader) return;
		busy = true;
		error = '';
		try {
			const order = ranked.map((r) => r.key);
			const fromCatalog = order.filter((url) => picks[url].sourceId === null);
			const created = fromCatalog.length
				? await unwrap(api.POST('/api/v1/catalog/sources', { body: fromCatalog }))
				: [];
			for (const s of created) picks[s.url].sourceId = s.id;
			const ids = order.map((url) => picks[url].sourceId).filter((x): x is number => x !== null);
			await unwrap(
				api.PUT('/api/v1/readers/{reader_id}', {
					params: { path: { reader_id: id } },
					body: { ...form, email: form.email || null }
				})
			);
			await unwrap(api.PUT('/api/v1/readers/{reader_id}/sources', { params: { path: { reader_id: id } }, body: ids }));
			await goto(`/readers/${id}?welcome=1`);
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}

	$effect(() => {
		void id;
		load();
	});
</script>

<svelte:head><title>{t('wizard.title')} · Eilkurier</title></svelte:head>

{#if error && !reader}
	<p class="container page-head alert error" role="alert">{t('common.error', { message: error })}</p>
{:else if !reader || !form || !catalog}
	<p class="container page-head" aria-live="polite">{t('common.loading')}</p>
{:else}
	<div class="container page-head">
		<p class="eyebrow">{t('wizard.for', { name: reader.name })}</p>
		<h1 bind:this={heading} tabindex="-1">{t(`wizard.h.${step}` as MessageKey)}</h1>
		<Stepper steps={stepKeys.map((k) => t(k))} current={step} />
	</div>

	<div class="band">
		<div class="container aside-layout">
			<aside class="stack">
				<h2 class="aside-title">{t(`wizard.aside.${step}` as MessageKey)}</h2>
				<p>{t(`wizard.explain.${step}` as MessageKey)}</p>
				<p class="alert"><Icon name="info" /><span>{t(`wizard.tip.${step}` as MessageKey)}</span></p>
			</aside>

			<div class="stack">
				{#if step === 0}
					<ul class="grid two plain-list" role="list">
						{#each topicList as topic (topic.category)}
							{@const rank = topics.indexOf(topic.category)}
							<li>
								<TopicCard
									{topic}
									rank={rank < 0 ? null : rank + 1}
									count={entriesOf(topic.category).length}
									ontoggle={() => toggleTopic(topic.category)}
								/>
							</li>
						{/each}
					</ul>
				{:else if step === 1}
					{#each topics as category (category)}
						{@const look = topicLook(category, topicList)}
						{@const total = entriesOf(category).length}
						<section class="card topic-{look.color}" aria-labelledby="t-{category}">
							<div class="card-head">
								<h2 id="t-{category}" class="topic-title"><Icon name={look.icon} />{look.title}</h2>
								<span class="small muted">
									{t('wizard.chosenOf', {
										chosen: selected.filter((u) => picks[u]?.category === category).length,
										total
									})}
								</span>
							</div>
							{#if total > 12}
								<div class="field filter">
									<label for="f-{category}">{t('wizard.filter')}</label>
									<input id="f-{category}" type="search" bind:value={filter[category]} placeholder={t('wizard.filterHint')} />
								</div>
							{/if}
							{#each groupsOf(category) as [group, entries] (group)}
								{#if group}<h3 class="group">{group}</h3>{/if}
								<ul class="grid two plain-list" role="list">
									{#each entries as entry (entry.url)}
										<li>
											<SourceCard
												name={entry.name}
												description={entry.description}
												language={entry.language}
												recommended={entry.recommended}
												color={look.color}
												selected={selected.includes(entry.url)}
												ontoggle={() => toggleSource(entry.url)}
											/>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="muted">{t('wizard.noMatch')}</p>
							{/each}
						</section>
					{/each}
					{#if ownSources.length}
						<section class="card topic-grey" aria-labelledby="t-own">
							<h2 id="t-own" class="topic-title"><Icon name="rss" />{t('wizard.own')}</h2>
							<ul class="grid two plain-list" role="list">
								{#each ownSources as own (own.url)}
									<li>
										<SourceCard
											name={own.name}
											description={own.description}
											color="grey"
											selected={selected.includes(own.url)}
											ontoggle={() => toggleSource(own.url)}
										/>
									</li>
								{/each}
							</ul>
						</section>
					{/if}
				{:else if step === 2}
					<div class="card">
						<RankList
							bind:items={ranked}
							onremove={(r) => {
								ranked = ranked.filter((x) => x.key !== r.key);
								selected = selected.filter((u) => u !== r.key);
							}}
						/>
						{#if ranked.length === 0}<p class="muted">{t('wizard.nothingChosen')}</p>{/if}
					</div>
				{:else}
					<section class="card stack" aria-labelledby="h-delivery">
						<h2 id="h-delivery">{t('delivery.title')}</h2>
						<DeliveryFields
							bind:form
							bind:reader
							telegramEnabled={status?.telegram ?? true}
							emailEnabled={status?.email ?? true}
						/>
					</section>
					<section class="card stack" aria-labelledby="h-style">
						<h2 id="h-style">{t('style.title')}</h2>
						<StyleFields bind:form details={false} />
					</section>
				{/if}

				{#if error}<p class="alert error" role="alert">{t('common.error', { message: error })}</p>{/if}

				<div class="row spread nav-buttons">
					{#if step > 0}
						<button class="btn secondary large" type="button" onclick={() => go(step - 1)}>
							<Icon name="left" />{t('wizard.back')}
						</button>
					{:else}
						<span></span>
					{/if}
					{#if step < 3}
						<button class="btn large" type="button" disabled={!canContinue} onclick={() => go(step + 1)}>
							{t('wizard.next')}<Icon name="right" />
						</button>
					{:else}
						<button class="btn large" type="button" disabled={busy || ranked.length === 0} onclick={finish}>
							<Icon name="check" />{t('wizard.finish')}
						</button>
					{/if}
				</div>
				{#if !canContinue}<p class="small muted right">{t(`wizard.need.${step}` as MessageKey)}</p>{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.eyebrow {
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--brand);
		margin: 0 0 0.25rem;
	}
	h1:focus {
		outline: none;
	}
	.aside-title {
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--brand);
		margin: 0;
	}
	.plain-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.topic-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--t);
	}
	.group {
		margin: 1.25rem 0 0.6rem;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted);
	}
	.filter {
		max-width: 22rem;
		margin-bottom: 0.5rem;
	}
	.nav-buttons {
		padding-top: 0.5rem;
	}
	.right {
		text-align: right;
	}
</style>
