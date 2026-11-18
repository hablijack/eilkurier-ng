<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, unwrap } from '$lib/api/client';
	import Icon from '$lib/components/Icon.svelte';
	import { chooseReader } from '$lib/household.svelte';
	import { t } from '$lib/i18n.svelte';

	let name = $state('');
	let error = $state('');
	let busy = $state(false);

	async function create(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = '';
		try {
			const reader = await unwrap(api.POST('/api/v1/readers', { body: { name: name.trim() } }));
			chooseReader(reader.id);
			await goto(`/readers/${reader.id}/setup`);
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}
</script>

<svelte:head><title>{t('newReader.title')} · Eilkurier</title></svelte:head>

<div class="container narrow page-head">
	<h1>{t('newReader.title')}</h1>
	<p class="lede">{t('newReader.lede')}</p>
	<form class="card stack" onsubmit={create}>
		<div class="field">
			<label for="name">{t('newReader.name')}</label>
			<input id="name" type="text" bind:value={name} required maxlength="80" autocomplete="given-name" />
			<span class="hint">{t('newReader.nameHint')}</span>
		</div>
		{#if error}<p class="alert error" role="alert">{t('common.error', { message: error })}</p>{/if}
		<div class="row spread">
			<a class="btn secondary" href="/">{t('common.cancel')}</a>
			<button class="btn large" type="submit" disabled={busy}>{t('newReader.start')}<Icon name="right" /></button>
		</div>
	</form>
</div>
