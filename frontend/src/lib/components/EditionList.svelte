<script lang="ts">
	import type { EditionSummary } from '$lib/api/client';
	import { formatDate, t, type MessageKey } from '$lib/i18n.svelte';

	let { editions, readerNames = {} }: { editions: EditionSummary[]; readerNames?: Record<number, string> } =
		$props();

	const badge: Record<string, string> = { done: 'ok', failed: 'danger', pending: 'warn', skipped: '' };
</script>

<ul class="plain">
	{#each editions as edition (edition.id)}
		<li class="row spread">
			<div class="grow">
				<strong>{[readerNames[edition.reader_id], t('editions.number', { number: edition.number }), formatDate(edition.issue_date)]
						.filter(Boolean)
						.join(' · ')}</strong>
				{#if edition.lead_headline}<br /><span class="muted">{edition.lead_headline}</span>{/if}
				<br />
				<span class="small muted"
					>{t('editions.edited', { edited: edition.edited_count, total: edition.story_count })}</span
				>
				<span class="badge {badge[edition.delivery_status]}"
					>{t(`editions.delivery.${edition.delivery_status}` as MessageKey)}</span
				>
				{#if edition.delivery_error}<br /><span class="small muted">{edition.delivery_error}</span>{/if}
			</div>
			<div class="row">
				<a class="btn secondary small" href="/editions/{edition.id}">{t('editions.read')}</a>
				<a class="btn secondary small" href="/api/v1/editions/{edition.id}/pdf" target="_blank" rel="noopener"
					>{t('editions.pdf')}</a
				>
			</div>
		</li>
	{/each}
</ul>
