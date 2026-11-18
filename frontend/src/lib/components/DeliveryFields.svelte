<script lang="ts">
	import { api, unwrap, type Reader, type ReaderIn } from '$lib/api/client';
	import { t, weekdays } from '$lib/i18n.svelte';
	import Icon from './Icon.svelte';

	let {
		form = $bindable(),
		reader = $bindable(),
		telegramEnabled = true,
		emailEnabled = true
	}: { form: ReaderIn; reader: Reader; telegramEnabled?: boolean; emailEnabled?: boolean } = $props();

	const channels = $derived(
		[
			{ value: 'none', icon: 'book', label: t('delivery.none'), hint: t('delivery.noneHint'), enabled: true },
			{ value: 'telegram', icon: 'send', label: 'Telegram', hint: t('delivery.telegramHint'), enabled: telegramEnabled },
			{ value: 'email', icon: 'mail', label: t('channel.email'), hint: t('delivery.emailHint'), enabled: emailEnabled }
		] as const
	);

	function toggleDay(day: number, on: boolean) {
		const days = new Set(form.delivery_days ?? []);
		if (on) days.add(day);
		else days.delete(day);
		form.delivery_days = [...days].sort();
	}

	async function renewCode() {
		reader = await unwrap(
			api.POST('/api/v1/readers/{reader_id}/telegram-link', { params: { path: { reader_id: reader.id } } })
		);
	}
</script>

<fieldset class="stack">
	<legend>{t('delivery.channel')}</legend>
	<div class="grid three">
		{#each channels as channel (channel.value)}
			<label class="option" class:disabled={!channel.enabled}>
				<input type="radio" name="channel" value={channel.value} bind:group={form.channel} disabled={!channel.enabled} />
				<span class="option-icon"><Icon name={channel.icon} /></span>
				<span class="option-label">{channel.label}</span>
				<span class="small muted">{channel.enabled ? channel.hint : t('delivery.notAvailable')}</span>
			</label>
		{/each}
	</div>
</fieldset>

{#if form.channel === 'email'}
	<div class="field">
		<label for="email">{t('delivery.email')}</label>
		<input id="email" type="email" autocomplete="email" bind:value={form.email} required />
	</div>
{/if}
{#if form.channel === 'telegram'}
	<div class="alert" aria-live="polite">
		<Icon name="info" />
		<div>
			{#if reader.telegram_linked}
				<p><span class="badge ok">{t('delivery.telegramLinked')}</span></p>
			{:else if reader.telegram_link_code}
				<p>{t('delivery.telegramCode')}</p>
				<p><span class="code">{reader.telegram_link_code}</span></p>
			{/if}
			<button class="btn secondary small" type="button" onclick={renewCode}>{t('delivery.telegramRenew')}</button>
		</div>
	</div>
{/if}

{#if form.channel !== 'none'}
	<div class="grid two">
		<div class="field">
			<label for="time">{t('delivery.time')}</label>
			<input id="time" type="time" bind:value={form.delivery_time} required />
		</div>
		<fieldset>
			<legend>{t('delivery.days')}</legend>
			<div class="days">
				{#each weekdays() as name, i (name)}
					<label class="check day">
						<input
							type="checkbox"
							checked={form.delivery_days?.includes(i + 1)}
							onchange={(e) => toggleDay(i + 1, e.currentTarget.checked)}
						/><span>{name}<span class="visually-hidden"> ({weekdays('long')[i]})</span></span>
					</label>
				{/each}
			</div>
		</fieldset>
	</div>
{/if}

<style>
	.option {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		padding: 1rem;
		border: 2px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		cursor: pointer;
		position: relative;
	}
	.option:has(input:checked) {
		border-color: var(--brand);
		background: var(--brand-tint);
	}
	.option:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
	}
	.option input {
		position: absolute;
		opacity: 0;
		inset: 0;
		cursor: pointer;
	}
	.option.disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.option-icon {
		color: var(--brand);
	}
	.option-label {
		font-weight: 700;
	}
	.day {
		gap: 0.35rem;
	}
</style>
