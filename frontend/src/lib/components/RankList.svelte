<script lang="ts" module>
	export type RankItem = { key: string; name: string; detail: string; color: string };
</script>

<script lang="ts">
	import { t } from '$lib/i18n.svelte';
	import { monogram } from '$lib/reader';
	import Icon from './Icon.svelte';

	let {
		items = $bindable(),
		onremove
	}: { items: RankItem[]; onremove?: (item: RankItem) => void } = $props();

	let announcement = $state('');
	let dragging = $state<number | null>(null);
	let over = $state<number | null>(null);

	function move(from: number, to: number) {
		if (to < 0 || to >= items.length || from === to) return;
		const next = [...items];
		const [item] = next.splice(from, 1);
		next.splice(to, 0, item);
		items = next;
		announcement = t('rank.moved', { name: item.name, position: to + 1, total: items.length });
	}

	function drop(index: number) {
		if (dragging !== null) move(dragging, index);
		dragging = null;
		over = null;
	}
</script>

<ol class="rank">
	{#each items as item, i (item.key)}
		<li
			class="topic-{item.color}"
			class:dragging={dragging === i}
			class:over={over === i && dragging !== i}
			draggable="true"
			ondragstart={(e) => {
				dragging = i;
				e.dataTransfer?.setData('text/plain', item.key);
			}}
			ondragover={(e) => {
				e.preventDefault();
				over = i;
			}}
			ondragleave={() => (over = over === i ? null : over)}
			ondrop={(e) => {
				e.preventDefault();
				drop(i);
			}}
			ondragend={() => {
				dragging = null;
				over = null;
			}}
		>
			<span class="grip" aria-hidden="true"><Icon name="grip" size={18} /></span>
			<span class="pos" aria-hidden="true">{i + 1}</span>
			<span class="mono" aria-hidden="true">{monogram(item.name)}</span>
			<span class="text">
				<span class="name">{item.name}</span>
				<span class="detail">{item.detail}</span>
			</span>
			<span class="actions">
				<button
					class="btn secondary icon small"
					type="button"
					disabled={i === 0}
					onclick={() => move(i, i - 1)}
					aria-label={t('rank.up', { name: item.name })}><Icon name="up" size={18} /></button
				>
				<button
					class="btn secondary icon small"
					type="button"
					disabled={i === items.length - 1}
					onclick={() => move(i, i + 1)}
					aria-label={t('rank.down', { name: item.name })}><Icon name="down" size={18} /></button
				>
				{#if onremove}
					<button
						class="btn ghost icon small"
						type="button"
						onclick={() => onremove(item)}
						aria-label={t('rank.remove', { name: item.name })}><Icon name="x" size={18} /></button
					>
				{/if}
			</span>
		</li>
	{/each}
</ol>
<p class="visually-hidden" role="status" aria-live="polite">{announcement}</p>

<style>
	.rank {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.6rem;
		background: var(--surface);
		border: 1px solid var(--line);
		border-left: 4px solid var(--t);
		border-radius: var(--radius-sm);
		cursor: grab;
	}
	li.dragging {
		opacity: 0.5;
	}
	li.over {
		border-color: var(--brand);
		box-shadow: 0 -3px 0 var(--brand);
	}
	.grip {
		color: var(--muted);
		display: none;
	}
	@media (pointer: fine) {
		.grip {
			display: inline-flex;
		}
	}
	.pos {
		width: 1.6rem;
		text-align: center;
		font-weight: 800;
		color: var(--muted);
	}
	li:first-child .pos {
		color: var(--brand);
	}
	.mono {
		display: grid;
		place-items: center;
		flex: none;
		width: 36px;
		height: 36px;
		border-radius: 8px;
		background: var(--t);
		color: var(--surface);
		font-weight: 800;
		font-size: 0.8rem;
	}
	.text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.name {
		font-weight: 650;
	}
	.detail {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.actions {
		display: flex;
		gap: 0.25rem;
		flex: none;
	}
</style>
