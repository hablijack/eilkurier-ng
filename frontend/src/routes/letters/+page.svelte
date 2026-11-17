<script lang="ts">
	import { onMount } from 'svelte';
	import { api, unwrap, type Letter } from '$lib/api/client';
	import { formatDateTime, t, type MessageKey } from '$lib/i18n.svelte';

	let letters = $state<Letter[]>([]);
	let author = $state('');
	let text = $state('');
	let message = $state('');
	let error = $state('');

	async function load() {
		letters = await unwrap(api.GET('/api/v1/letters'));
	}

	async function send(event: SubmitEvent) {
		event.preventDefault();
		error = '';
		try {
			await unwrap(api.POST('/api/v1/letters', { body: { author: author.trim(), text: text.trim() } }));
			text = '';
			message = t('letters.sent');
			try {
				localStorage.setItem('eilkurier.author', author);
			} catch {
				/* storage unavailable */
			}
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function remove(letter: Letter) {
		await api.DELETE('/api/v1/letters/{letter_id}', { params: { path: { letter_id: letter.id } } });
		await load();
	}

	onMount(() => {
		try {
			author = localStorage.getItem('eilkurier.author') ?? '';
		} catch {
			/* storage unavailable */
		}
		load();
	});
</script>

<svelte:head><title>{t('letters.title')} · Eilkurier</title></svelte:head>

<div class="stack">
	<h1>{t('letters.title')}</h1>
	<p class="hint">{t('letters.hint')}</p>

	<form class="card stack" onsubmit={send}>
		<div class="field">
			<label for="author">{t('letters.from')}</label>
			<input id="author" type="text" bind:value={author} required maxlength="80" autocomplete="name" />
		</div>
		<div class="field">
			<label for="text">{t('letters.text')}</label>
			<textarea id="text" bind:value={text} required maxlength="1000"></textarea>
		</div>
		<div class="row">
			<button class="btn" type="submit">{t('letters.send')}</button>
			<span role="status" aria-live="polite">{message}</span>
		</div>
		{#if error}<p class="alert error" role="alert">{t('common.error', { message: error })}</p>{/if}
	</form>

	<section class="card">
		{#if letters.length === 0}
			<p class="muted">{t('letters.empty')}</p>
		{:else}
			<ul class="plain">
				{#each letters as letter (letter.id)}
					<li class="row spread">
						<blockquote class="grow">
							<p>„{letter.text}“</p>
							<footer class="small muted">
								— {letter.author}, {formatDateTime(letter.created_at)}, {t(`letters.via.${letter.via}` as MessageKey)}
							</footer>
						</blockquote>
						<button class="btn danger small" type="button" onclick={() => remove(letter)}
							>{t('common.delete')}<span class="visually-hidden">: {letter.text.slice(0, 30)}</span></button
						>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>

<style>
	blockquote {
		margin: 0;
		font-family: var(--font-body);
		font-style: italic;
	}
	blockquote p {
		margin: 0 0 0.25rem;
	}
	blockquote footer {
		font-style: normal;
		font-family: var(--font-ui);
	}
</style>
