<script lang="ts">
	import { avatarColor, initials } from '$lib/household.svelte';

	let { id, name, size = 48 }: { id: number; name: string; size?: number } = $props();
</script>

<span class="avatar topic-{avatarColor(id)}" style:--size="{size}px" aria-hidden="true">{initials(name)}</span>

<style>
	.avatar {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--size);
		height: var(--size);
		border-radius: 50%;
		background: var(--t-tint);
		color: var(--t);
		font-weight: 700;
		font-size: calc(var(--size) * 0.38);
		letter-spacing: 0.02em;
	}
</style>
