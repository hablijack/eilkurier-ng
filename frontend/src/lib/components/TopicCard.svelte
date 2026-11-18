<script lang="ts">
	import type { CatalogTopic } from '$lib/api/client';
	import { t } from '$lib/i18n.svelte';
	import { topicLook } from '$lib/reader';
	import Icon from './Icon.svelte';

	let {
		topic,
		rank,
		count,
		ontoggle
	}: { topic: CatalogTopic; rank: number | null; count: number; ontoggle: () => void } = $props();

	const look = $derived(topicLook(topic.category, [topic]));
</script>

<button class="topic topic-{look.color}" type="button" aria-pressed={rank !== null} onclick={ontoggle}>
	<span class="icon"><Icon name={look.icon} size={26} /></span>
	<span class="body">
		<span class="title">{topic.title}</span>
		<span class="desc">{topic.description}</span>
		<span class="count">{t('wizard.sourceCount', { count })}</span>
	</span>
	<span class="state" aria-hidden="true">
		{#if rank !== null}{rank}{:else}<Icon name="plus" size={18} />{/if}
	</span>
</button>

<style>
	.topic {
		display: flex;
		align-items: flex-start;
		gap: 0.9rem;
		width: 100%;
		height: 100%;
		padding: 1rem;
		text-align: left;
		font: inherit;
		color: var(--ink);
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
		cursor: pointer;
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.topic:hover {
		border-color: var(--t);
	}
	.topic[aria-pressed='true'] {
		border-color: var(--t);
		background: var(--t-tint);
	}
	.icon {
		display: grid;
		place-items: center;
		flex: none;
		width: 52px;
		height: 52px;
		border-radius: 14px;
		background: var(--t-tint);
		color: var(--t);
	}
	.topic[aria-pressed='true'] .icon {
		background: var(--surface);
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		flex: 1;
		min-width: 0;
	}
	.title {
		font-weight: 700;
		font-size: 1.1rem;
	}
	.desc {
		color: var(--muted);
		font-size: 0.95rem;
	}
	.count {
		color: var(--t);
		font-size: 0.85rem;
		font-weight: 600;
	}
	.state {
		display: grid;
		place-items: center;
		flex: none;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		border: 2px solid var(--line-strong);
		color: var(--muted);
		font-weight: 700;
	}
	.topic[aria-pressed='true'] .state {
		background: var(--t);
		border-color: var(--t);
		color: var(--surface);
	}
</style>
