<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		api,
		unwrap,
		type EditionSummary,
		type Interest,
		type Reader,
		type ReaderIn,
		type Source
	} from '$lib/api/client';
	import EditionList from '$lib/components/EditionList.svelte';
	import { t, weekdays, type MessageKey } from '$lib/i18n.svelte';

	const id = $derived(Number(page.params.id));

	let reader = $state<Reader | null>(null);
	let form = $state<ReaderIn | null>(null);
	let interests = $state<Interest[]>([]);
	let selectedSources = $state<number[]>([]);
	let sources = $state<Source[]>([]);
	let editions = $state<EditionSummary[]>([]);
	let message = $state('');
	let error = $state('');
	let busy = $state(false);
	let newTerm = $state('');
	let newWeight = $state(1);

	const themes = ['klassisch', 'feuilleton', 'grossdruck'] as const;
	const weights = [3, 2, 1, -1, -2];
	const categories = $derived([...new Set(sources.map((s) => s.category))]);

	async function load() {
		try {
			const [r, s, e] = await Promise.all([
				unwrap(api.GET('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } } })),
				unwrap(api.GET('/api/v1/sources')),
				unwrap(api.GET('/api/v1/editions', { params: { query: { reader_id: id } } }))
			]);
			setReader(r);
			sources = s;
			editions = e;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function setReader(r: Reader) {
		reader = r;
		const { id: _id, telegram_linked, telegram_link_code, interests: i, source_ids, ...rest } = r;
		form = { ...rest, delivery_time: (rest.delivery_time ?? '06:00').slice(0, 5) };
		// snap to the UI's weight steps (the API accepts any value from -3 to 3)
		interests = i.map((x) => ({ ...x, weight: Math.max(-2, Math.min(3, Math.round(x.weight ?? 1))) || 1 }));
		selectedSources = [...source_ids];
	}

	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (!form) return;
		busy = true;
		message = '';
		error = '';
		try {
			const body = { ...form, email: form.email || null };
			await unwrap(api.PUT('/api/v1/readers/{reader_id}', { params: { path: { reader_id: id } }, body }));
			await unwrap(
				api.PUT('/api/v1/readers/{reader_id}/interests', { params: { path: { reader_id: id } }, body: interests })
			);
			setReader(
				await unwrap(
					api.PUT('/api/v1/readers/{reader_id}/sources', {
						params: { path: { reader_id: id } },
						body: selectedSources
					})
				)
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

	function toggleDay(day: number, on: boolean) {
		if (!form) return;
		const days = new Set(form.delivery_days ?? []);
		if (on) days.add(day);
		else days.delete(day);
		form.delivery_days = [...days].sort();
	}

	async function renewCode() {
		setReader(
			await unwrap(api.POST('/api/v1/readers/{reader_id}/telegram-link', { params: { path: { reader_id: id } } }))
		);
	}

	async function createEdition(send: boolean) {
		busy = true;
		message = '';
		error = '';
		try {
			const edition = await unwrap(
				api.POST('/api/v1/readers/{reader_id}/editions', {
					params: { path: { reader_id: id }, query: { send } }
				})
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
		await goto('/');
	}

	$effect(() => {
		void id;
		load();
	});
</script>

<svelte:head><title>{reader?.name ?? ''} · Eilkurier</title></svelte:head>

{#if error && !reader}
	<p class="alert error" role="alert">{t('common.error', { message: error })}</p>
{:else if !reader || !form}
	<p aria-live="polite">{t('common.loading')}</p>
{:else}
	<form class="stack" onsubmit={save}>
		<h1>{reader.name}</h1>

		<div class="grid two">
			<fieldset class="stack">
				<legend>{t('profile.title')}</legend>
				<div class="field">
					<label for="name">{t('profile.name')}</label>
					<input id="name" type="text" bind:value={form.name} required maxlength="80" />
				</div>
				<div class="field">
					<label for="theme">{t('profile.theme')}</label>
					<select id="theme" bind:value={form.theme}>
						{#each themes as theme (theme)}<option value={theme}>{t(`theme.${theme}`)}</option>{/each}
					</select>
					<a class="small" href="/api/v1/samples/edition.pdf?theme={form.theme}" target="_blank" rel="noopener"
						>{t('profile.preview')}</a
					>
				</div>
				<div class="grid two">
					<div class="field">
						<label for="language">{t('profile.language')}</label>
						<select id="language" bind:value={form.language}>
							<option value="de">Deutsch</option>
							<option value="en">English</option>
						</select>
					</div>
					<div class="field">
						<label for="paper">{t('profile.paper')}</label>
						<select id="paper" bind:value={form.paper}>
							<option value="a4">A4</option>
							<option value="a5">A5</option>
							<option value="a3">A3</option>
						</select>
					</div>
					<div class="field">
						<label for="font-scale">{t('profile.fontScale')}</label>
						<select id="font-scale" bind:value={form.font_scale}>
							{#each [0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5] as scale (scale)}
								<option value={scale}>{Math.round(scale * 100)} %</option>
							{/each}
						</select>
					</div>
					<div class="field">
						<label for="story-count">{t('profile.storyCount')}</label>
						<input id="story-count" type="number" min="3" max="15" bind:value={form.story_count} />
					</div>
				</div>
				<label class="check"><input type="checkbox" bind:checked={form.paper_tint} />{t('profile.paperTint')}</label>
				<label class="check"><input type="checkbox" bind:checked={form.active} />{t('profile.active')}</label>
			</fieldset>

			<fieldset class="stack">
				<legend>{t('delivery.title')}</legend>
				<div class="field">
					<label for="channel">{t('delivery.channel')}</label>
					<select id="channel" bind:value={form.channel}>
						{#each ['telegram', 'email', 'none'] as channel (channel)}
							<option value={channel}>{t(`channel.${channel}` as MessageKey)}</option>
						{/each}
					</select>
				</div>
				{#if form.channel === 'email'}
					<div class="field">
						<label for="email">{t('delivery.email')}</label>
						<input id="email" type="email" autocomplete="email" bind:value={form.email} required />
					</div>
				{/if}
				{#if form.channel === 'telegram'}
					<div class="card" aria-live="polite">
						{#if reader.telegram_linked}
							<p><span class="badge ok">{t('delivery.telegramLinked')}</span></p>
						{:else if reader.telegram_link_code}
							<p>{t('delivery.telegramCode')}</p>
							<p><span class="code">{reader.telegram_link_code}</span></p>
						{/if}
						<button class="btn secondary small" type="button" onclick={renewCode}>{t('delivery.telegramRenew')}</button>
					</div>
				{/if}
				<div class="field">
					<label for="time">{t('delivery.time')}</label>
					<input id="time" type="time" bind:value={form.delivery_time} required />
				</div>
				<fieldset>
					<legend>{t('delivery.days')}</legend>
					<div class="days">
						{#each weekdays('long') as name, i (name)}
							<label class="check">
								<input
									type="checkbox"
									checked={form.delivery_days?.includes(i + 1)}
									onchange={(e) => toggleDay(i + 1, e.currentTarget.checked)}
								/>{name}
							</label>
						{/each}
					</div>
				</fieldset>
			</fieldset>
		</div>

		<fieldset class="stack">
			<legend>{t('interests.title')}</legend>
			<p class="hint">{t('interests.hint')}</p>
			{#if interests.length === 0}<p class="muted">{t('interests.empty')}</p>{/if}
			<ul class="plain">
				{#each interests as interest, i (interest.term)}
					<li class="row">
						<span class="grow">{interest.term}</span>
						<label class="visually-hidden" for="w-{i}">{t('interests.weight')}: {interest.term}</label>
						<select id="w-{i}" bind:value={interest.weight} class="weight">
							{#each weights as w (w)}<option value={w}>{t(`interests.w.${w}` as MessageKey)}</option>{/each}
						</select>
						<button
							class="btn danger small"
							type="button"
							onclick={() => (interests = interests.filter((x) => x !== interest))}
							aria-label="{t('common.remove')}: {interest.term}">✕</button
						>
					</li>
				{/each}
			</ul>
			<div class="row">
				<div class="field grow">
					<label for="new-term">{t('interests.term')}</label>
					<input
						id="new-term"
						type="text"
						bind:value={newTerm}
						maxlength="80"
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
				<button class="btn secondary add" type="button" onclick={addInterest}>{t('common.add')}</button>
			</div>
		</fieldset>

		<fieldset class="stack">
			<legend>{t('sources.mine')}</legend>
			<p class="hint">{t('sources.mineHint')} <a href="/sources">{t('nav.sources')}</a></p>
			{#each categories as category (category)}
				<fieldset>
					<legend>{category}</legend>
					<div class="grid two">
						{#each sources.filter((s) => s.category === category) as source (source.id)}
							<label class="check">
								<input type="checkbox" value={source.id} bind:group={selectedSources} />{source.name}
							</label>
						{/each}
					</div>
				</fieldset>
			{/each}
		</fieldset>

		<div class="row sticky-save">
			<button class="btn" type="submit" disabled={busy}>{t('common.save')}</button>
			<span role="status" aria-live="polite">
				{#if message}{message}{/if}
			</span>
			{#if error}<span class="alert error" role="alert">{t('common.error', { message: error })}</span>{/if}
		</div>
	</form>

	<section class="card stack" aria-labelledby="editions">
		<h2 id="editions">{t('editions.title')}</h2>
		<div class="row">
			<button class="btn" type="button" disabled={busy} onclick={() => createEdition(false)}>{t('editions.createNow')}</button>
			{#if form.channel !== 'none'}
				<button class="btn secondary" type="button" disabled={busy} onclick={() => createEdition(true)}
					>{t('editions.createAndSend')}</button
				>
			{/if}
		</div>
		<EditionList {editions} />
	</section>

	<p><button class="btn danger" type="button" onclick={remove}>{t('reader.delete')}</button></p>
{/if}

<style>
	.weight {
		width: auto;
	}
	.add {
		align-self: flex-end;
	}
	.sticky-save {
		position: sticky;
		bottom: 0;
		background: var(--paper);
		padding: 0.75rem 0;
		border-top: 1px solid var(--line);
	}
</style>
