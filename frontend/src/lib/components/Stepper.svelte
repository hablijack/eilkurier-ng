<script lang="ts">
	import { t } from '$lib/i18n.svelte';
	import Icon from './Icon.svelte';

	let { steps, current }: { steps: string[]; current: number } = $props();
</script>

<p class="mobile-label" aria-hidden="true">{t('wizard.stepOf', { step: current + 1, total: steps.length })} · {steps[current]}</p>
<ol class="stepper">
	{#each steps as label, i (label)}
		<li class:done={i < current} class:active={i === current} aria-current={i === current ? 'step' : undefined}>
			<span class="dot">
				{#if i < current}<Icon name="check" size={16} />{:else}{i + 1}{/if}
			</span>
			<span class="label">{label}</span>
		</li>
	{/each}
</ol>

<style>
	.stepper {
		display: flex;
		list-style: none;
		margin: 0;
		padding: 0;
		gap: 0.25rem;
	}
	li {
		flex: 1 1 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
		color: var(--muted);
		font-weight: 600;
		font-size: 0.95rem;
	}
	li + li::before {
		content: '';
		flex: 0 1 2rem;
		height: 2px;
		background: var(--line);
		margin-right: 0.25rem;
	}
	li.done + li::before,
	li.active::before {
		background: var(--brand);
	}
	.dot {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		border: 2px solid var(--line-strong);
		background: var(--surface);
		font-size: 0.9rem;
	}
	.active,
	.done {
		color: var(--ink);
	}
	.active .dot {
		border-color: var(--brand);
		color: var(--brand);
	}
	.done .dot {
		border-color: var(--brand);
		background: var(--brand);
		color: var(--brand-ink);
	}
	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.mobile-label {
		display: none;
	}
	@media (max-width: 40rem) {
		.mobile-label {
			display: block;
			font-weight: 600;
			color: var(--muted);
			margin: 0 0 0.5rem;
		}
		li + li::before {
			flex: 1 1 auto;
		}
		li {
			flex: 1 1 auto;
		}
		li:first-child {
			flex: 0 0 auto;
		}
		.label {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0 0 0 0);
		}
	}
</style>
