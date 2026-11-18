<script lang="ts">
	import { t } from '$lib/i18n.svelte';
	import { monogram } from '$lib/reader';
	import Icon from './Icon.svelte';

	let {
		name,
		description,
		language = 'de',
		recommended = false,
		color,
		selected,
		ontoggle
	}: {
		name: string;
		description: string;
		language?: string;
		recommended?: boolean;
		color: string;
		selected: boolean;
		ontoggle: () => void;
	} = $props();
</script>

<button class="source topic-{color}" type="button" aria-pressed={selected} onclick={ontoggle}>
	<span class="mono" aria-hidden="true">{monogram(name)}</span>
	<span class="body">
		<span class="name">{name}</span>
		<span class="desc">{description}</span>
		{#if recommended || language !== 'de'}
			<span class="tags">
				{#if recommended}<span class="badge info"><Icon name="star" size={12} />{t('wizard.recommended')}</span>{/if}
				{#if language !== 'de'}<span class="badge">{t('wizard.english')}</span>{/if}
			</span>
		{/if}
	</span>
	<span class="state" aria-hidden="true"><Icon name={selected ? 'check' : 'plus'} size={18} /></span>
</button>

<style>
	.source {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		width: 100%;
		height: 100%;
		padding: 0.85rem;
		text-align: left;
		font: inherit;
		color: var(--ink);
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
		cursor: pointer;
		transition: border-color 0.15s;
	}
	.source:hover {
		border-color: var(--t);
	}
	.source[aria-pressed='true'] {
		border-color: var(--t);
		background: var(--t-tint);
	}
	.mono {
		display: grid;
		place-items: center;
		flex: none;
		width: 44px;
		height: 44px;
		border-radius: 10px;
		background: var(--t);
		color: var(--surface);
		font-weight: 800;
		font-size: 0.95rem;
		letter-spacing: 0.03em;
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		flex: 1;
		min-width: 0;
	}
	.name {
		font-weight: 700;
	}
	.desc {
		color: var(--muted);
		font-size: 0.9rem;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.2rem;
	}
	.state {
		display: grid;
		place-items: center;
		flex: none;
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 2px solid var(--line-strong);
		color: var(--muted);
	}
	.source[aria-pressed='true'] .state {
		background: var(--t);
		border-color: var(--t);
		color: var(--surface);
	}
</style>
