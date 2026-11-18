import type { CatalogTopic, Reader } from '$lib/api/client';
import { isIcon, type IconName } from '$lib/components/Icon.svelte';
import { t, weekdays, type MessageKey } from '$lib/i18n.svelte';

/** "Daily at 06:00 · Telegram" */
export function deliveryText(reader: Reader): string {
	if (!reader.active) return t('reader.inactive');
	if (reader.channel === 'none') return t('reader.noDelivery');
	const days =
		reader.delivery_days?.length === 7
			? t('days.daily')
			: (reader.delivery_days ?? []).map((d) => weekdays()[d - 1]).join(', ');
	return t('reader.delivery', {
		days,
		time: (reader.delivery_time ?? '06:00').slice(0, 5),
		channel: t(`channel.${reader.channel}` as MessageKey)
	});
}

export const themes = ['klassisch', 'feuilleton', 'grossdruck'] as const;

/** Display data for a section: its catalog topic, or a neutral fallback for own sources. */
export function topicLook(
	category: string,
	topics: CatalogTopic[]
): { title: string; icon: IconName; color: string } {
	const topic = topics.find((x) => x.category === category);
	if (!topic) return { title: category, icon: 'rss', color: 'grey' };
	return {
		title: topic.title,
		icon: isIcon(topic.icon) ? topic.icon : 'rss',
		color: topic.color
	};
}

/** Two letters for a source's tile, e.g. "heise online News" → "HO". */
export function monogram(name: string): string {
	const words = name
		.replace(/[^\p{L}\p{N} ]/gu, ' ')
		.split(/\s+/)
		.filter(Boolean);
	return ((words[0]?.[0] ?? '?') + (words[1]?.[0] ?? words[0]?.[1] ?? '')).toUpperCase();
}
