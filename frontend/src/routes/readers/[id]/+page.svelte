<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		api,
		unwrap,
		type CatalogTopic,
		type EditionSummary,
		type Interest,
		type Reader,
		type ReaderIn,
		type Source,
		type SystemStatus
	} from '$lib/api/client';
	import Avatar from '$lib/components/Avatar.svelte';
	import DeliveryFields from '$lib/components/DeliveryFields.svelte';
	import EditionList from '$lib/components/EditionList.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RankList, { type RankItem } from '$lib/components/RankList.svelte';
	import StyleFields from '$lib/components/StyleFields.svelte';
	import { chooseReader } from '$lib/household.svelte';
	import { t, type MessageKey } from '$lib/i18n.svelte';
	import { deliveryText, topicLook } from '$lib/reader';

	const id = $derived(Number(page.params.id));
	const welcome = $derived(page.url.searchParams.has('welcome'));

	let reader = $state<Reader | null>(null);
	let form = $state<ReaderIn | null>(null);
	let interests = $state<Interest[]>([]);
	let ranked = $state<RankItem[]>([]);
	let sources = $state<Source[]>([]);
	let topics = $state<CatalogTopic[]>([]);
	let status = $state<SystemStatus | null>(null);
	let editions = $state<EditionSummary[]>([]);
	let saved = $state('');
	let message = $state('');
	let error = $state('');
	let busy = $state(false);
	let newTerm = $state('');
	let newWeight = $state(2);

	const weights = [3, 2, 1, -1, -2];
	const snapshot = () => JSON.stringify([form, interests, ranked.map((r) => r.key)]);
	const dirty = $derived(reader !== null && snapshot() !== saved);

	async function load() {
		try {
			const [r, s, c, st, e] = await Promise.all([
				unwrap(api.GET('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } } })),
				unwrap(api.GET('/api/v1/sources')),
				unwrap(api.GET('/api/v1/catalog')),
				unwrap(api.GET('/api/v1/status')),
				unwrap(api.GET('/api/v1/editions', { params: { query: { reader_id: id } } }))
			]);
			sources = s;
			topics = c.topics;
			status = st;
			editions = e;
			setReader(r);
			chooseReader(r.id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function setReader(r: Reader) {
		reader = r;
		const { id: _id, telegram_linked, telegram_link_code, interests: i, source_ids, ...rest } = r;
		form = { ...rest, delivery_time: (rest.delivery_time ?? '06:00').slice(0, 5) };
		// snap to the UI's weight steps (the API accepts any value from -2 to 3)
		interests = i.map((x) => ({ ...x, weight: Math.max(-2, Math.min(3, Math.round(x.weight ?? 1))) || 1 }));
		ranked = source_ids
			.map((sid) => sources.find((s) => s.id === sid))
			.filter((s): s is Source => !!s)
			.map((s) => {
				const look = topicLook(s.category, topics);
				return { key: String(s.id), name: s.name, detail: look.title, color: look.color };
			});
		saved = snapshot();
	}

	async function save(event?: SubmitEvent) {
		event?.preventDefault();
		if (!form) return;
		busy = true;
		message = '';
		error = '';
		try {
			const path = { params: { path: { reader_id: id } } };
			await unwrap(api.PUT('/api/v1/readers/{reader_id}', { ...path, body: { ...form, email: form.email || null } }));
			await unwrap(api.PUT('/api/v1/readers/{reader_id}/interests', { ...path, body: interests }));
			setReader(
				await unwrap(api.PUT('/api/v1/readers/{reader_id}/sources', { ...path, body: ranked.map((r) => Number(r.key)) }))
			);
			message = t('common.saved');
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	function addInterest() {
		const term = newTerm.trim();
		if (term.length < 2 || interests.some((i) => i.term.toLowerCase() === term.toLowerCase())) return;
		interests = [...interests, { term, weight: newWeight }];
		newTerm = '';
	}

	async function createEdition(send: boolean) {
		busy = true;
		message = '';
		error = '';
		try {
			const edition = await unwrap(
				api.POST('/api/v1/readers/{reader_id}/editions', { params: { path: { reader_id: id }, query: { send } } })
			);
			message = t('editions.created', { number: edition.number });
			editions = await unwrap(api.GET('/api/v1/editions', { params: { query: { reader_id: id } } }));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!reader || !confirm(t('reader.deleteConfirm', { name: reader.name }))) return;
		await api.DELETE('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } } });
		chooseReader(null);
		await goto('/');
	}

	$effect(() => {
		void id;
		load();
	});
</script>

<svelte:head><title>{reader?.name ?? ''} · Eilkurier</title></svelte:head>

{#if error && !reader}
	<p class="container page-head alert error" role="alert">{t('common.error', { message: error })}</p>
{:else if !reader || !form}
	<p class="container page-head" aria-live="polite">{t('common.loading')}</p>
{:else}
	<div class="container page-head">
		<div class="profile-head">
			<Avatar id={reader.id} name={reader.name} size={72} />
			<div class="grow">
				<p class="eyebrow">{t('mine.eyebrow')}</p>
				<h1>{reader.name}</h1>
				<p class="muted">{deliveryText(reader)}</p>
			</div>
			<div class="row">
				<button class="btn" type="button" disabled={busy} onclick={() => createEdition(false)}>
					<Icon name="newspaper" />{t('editions.createNow')}
				</button>
				<a class="btn secondary" href="/readers/{reader.id}/setup"><Icon name="sliders" />{t('mine.wizard')}</a>
			</div>
		</div>
		{#if welcome}
			<p class="alert ok welcome" role="status">
				<Icon name="check" /><span><strong>{t('mine.welcomeTitle')}</strong> {t('mine.welcomeText')}</span>
			</p>
		{/if}
	</div>

	<form class="band paper" onsubmit={save}>
		<div class="container settings">
			<section class="card stack" aria-labelledby="h-sources">
				<div class="card-head">
					<h2 id="h-sources"><Icon name="newspaper" /> {t('mine.sources')}</h2>
					<a class="btn ghost small" href="/readers/{reader.id}/setup?step=1"><Icon name="plus" size={18} />{t('mine.addSources')}</a>
				</div>
				<p class="hint">{t('mine.sourcesHint')}</p>
				{#if ranked.length}
					<RankList bind:items={ranked} onremove={(r) => (ranked = ranked.filter((x) => x.key !== r.key))} />
				{:else}
					<p class="muted">{t('mine.noSources')}</p>
				{/if}
			</section>

			<section class="card stack" aria-labelledby="h-wishes">
				<h2 id="h-wishes"><Icon name="heart" /> {t('interests.title')}</h2>
				<p class="hint">{t('interests.hint')}</p>
				{#if interests.length === 0}<p class="muted">{t('interests.empty')}</p>{/if}
				<ul class="wishes">
					{#each interests as interest, i (interest.term)}
						<li class:negative={(interest.weight ?? 1) < 0}>
							<span class="term">{interest.term}</span>
							<label class="visually-hidden" for="w-{i}">{t('interests.weight')}: {interest.term}</label>
							<select id="w-{i}" bind:value={interest.weight}>
								{#each weights as w (w)}<option value={w}>{t(`interests.w.${w}` as MessageKey)}</option>{/each}
							</select>
							<button
								class="btn ghost icon small"
								type="button"
								onclick={() => (interests = interests.filter((x) => x !== interest))}
								aria-label="{t('common.remove')}: {interest.term}"><Icon name="x" size={18} /></button
							>
						</li>
					{/each}
				</ul>
				<div class="row add-wish">
					<div class="field grow">
						<label for="new-term">{t('interests.term')}</label>
						<input
							id="new-term"
							type="text"
							bind:value={newTerm}
							maxlength="80"
							placeholder={t('interests.placeholder')}
							onkeydown={(e) => {
								if (e.key === 'Enter') {
									e.preventDefault();
									addInterest();
								}
							}}
						/>
					</div>
					<div class="field">
						<label for="new-weight">{t('interests.weight')}</label>
						<select id="new-weight" bind:value={newWeight}>
							{#each weights as w (w)}<option value={w}>{t(`interests.w.${w}` as MessageKey)}</option>{/each}
						</select>
					</div>
					<button class="btn secondary" type="button" onclick={addInterest}><Icon name="plus" size={18} />{t('common.add')}</button>
				</div>
			</section>

			<section class="card stack" aria-labelledby="h-delivery">
				<h2 id="h-delivery"><Icon name="send" /> {t('delivery.title')}</h2>
				<DeliveryFields bind:form bind:reader telegramEnabled={status?.telegram ?? true} emailEnabled={status?.email ?? true} />
				<label class="check"><input type="checkbox" bind:checked={form.active} />{t('profile.active')}</label>
			</section>

			<section class="card stack" aria-labelledby="h-style">
				<h2 id="h-style"><Icon name="type" /> {t('style.title')}</h2>
				<div class="field">
					<label for="name">{t('profile.name')}</label>
					<input id="name" type="text" bind:value={form.name} required maxlength="80" />
				</div>
				<StyleFields bind:form />
			</section>

			<div class="save-bar" class:dirty>
				<button class="btn large" type="submit" disabled={busy || !dirty}><Icon name="check" />{t('common.save')}</button>
				<span role="status" aria-live="polite">{#if dirty}{t('mine.unsaved')}{:else}{message}{/if}</span>
				{#if error}<span class="alert error" role="alert">{t('common.error', { message: error })}</span>{/if}
			</div>
		</div>
	</form>

	<div class="container settings below">
		<section class="card stack" aria-labelledby="h-editions">
			<div class="card-head">
				<h2 id="h-editions"><Icon name="book" /> {t('editions.title')}</h2>
				{#if form.channel !== 'none'}
					<button class="btn secondary small" type="button" disabled={busy} onclick={() => createEdition(true)}>
						<Icon name="send" size={18} />{t('editions.createAndSend')}
					</button>
				{/if}
			</div>
			{#if editions.length}
				<EditionList {editions} />
			{:else}
				<p class="muted">{t('mine.noEditions')}</p>
			{/if}
		</section>

		<section class="danger-zone" aria-labelledby="h-danger">
			<h2 id="h-danger" class="visually-hidden">{t('reader.delete')}</h2>
			<button class="btn danger" type="button" onclick={remove}><Icon name="trash" size={18} />{t('reader.delete')}</button>
		</section>
	</div>
{/if}

<style>
	.profile-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem 1.25rem;
	}
	.profile-head .grow {
		flex: 1 1 14rem;
		min-width: 0;
	}
	.profile-head h1 {
		margin: 0;
	}
	.eyebrow {
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--brand);
		margin: 0;
	}
	.welcome {
		margin-top: 1.25rem;
	}
	.settings {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}
	.settings > .card {
		max-width: 52rem;
	}
	.below {
		padding-top: 2rem;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.wishes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.wishes li {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.2rem 0.2rem 0.2rem 0.9rem;
		border-radius: 999px;
		background: var(--ok-tint);
		border: 1px solid var(--line);
	}
	.wishes li.negative {
		background: var(--danger-tint);
	}
	.wishes .term {
		font-weight: 650;
	}
	.wishes select {
		width: auto;
		min-height: 36px;
		padding: 0.2rem 0.4rem;
		border: 0;
		background: transparent;
	}
	.add-wish {
		align-items: flex-end;
	}
	.save-bar {
		position: sticky;
		bottom: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		max-width: 52rem;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow-lg);
	}
	.save-bar.dirty {
		border-color: var(--brand);
	}
	.danger-zone {
		padding-top: 0.5rem;
	}
</style>
